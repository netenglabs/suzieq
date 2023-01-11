import logging
import os
import re
import tarfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import repeat
from typing import List

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from suzieq.db.parquet.dataset_utils import move_broken_file
from suzieq.db.parquet.migratedb import generic_migration, get_migrate_fn
from suzieq.shared.schema import SchemaForTable
from suzieq.shared.utils import humanize_timestamp


class SqCoalesceState:
    '''Class that coalesces parquet files'''

    def __init__(self, logger: str, period: timedelta):
        self.current_df = pd.DataFrame()
        self.logger = logger if logger else logging.getLogger()
        self.keys = None        # filled as we tackle each table
        self.schema = None      # filled as we tackle each table
        self.dbeng = None       # filled as we tackle each table
        self.period = period
        self.prefix = 'sqc-h-'   # sqc == suzieq coalesceer, h: hourly coalesce
        self.ign_pfx = ['.', '_', 'sqc-']  # Prefixes to ignore for coalesceing
        self.wrfile_count = 0
        self.wrrec_count = 0
        self.block_start = self.block_end = 0

    @ property
    def pq_file_name(self):
        """Callback to create a filename that uses the timestamp of start
        of hour. This makes it easy for us to lookup data when we need to.

        :returns: parquet filename to write
        :rtype: str

        """
        # Using timestamp rather than date/time string to simplify reads
        name_suffix = f'{self.block_start}-{self.block_end}.parquet'

        # {i} is replaced by pyarrow with a sequential number. It must be
        # provided when a name for the output parquet file is provided
        return f'{self.prefix}' + '{i}-' + name_suffix


def archive_coalesced_files(filelist: List[str], outfolder: str,
                            state: SqCoalesceState, dodel: bool) -> None:
    """Tars and removes the already coalesced files

    :param filelist: List{str], list of files to be tarred and archived
    :param outfolder: str, folder name where the archive is to be stored
    :param state: SqCoalesceState, state of coalesceer
    :param dodel: bool, True if the coalesced files must be deleted
    :returns: Nothing
    """
    if filelist and outfolder:
        with tarfile.open(f'{outfolder}/_archive-{state.prefix}-'
                          f'{state.block_start}-{state.block_end}.tar.bz2',
                          'w:bz2') as f:
            for file in filelist:
                f.add(file)
    if dodel:
        # pylint: disable=expression-not-assigned
        [os.remove(x) for x in filelist]


# pylint: disable=unused-argument
# Doing pylint override because I'm nervous about touching this fn
def write_files(table: str, filelist: List[str], in_basedir: str,
                outfolder: str, partition_cols: List[str],
                state: SqCoalesceState, block_start, block_end) -> None:
    """Write the data from the list of files out as a single coalesced block

    We're fixing the compression in this function
    :param table: str, Name of the table for which we're writing the files
    :param filelist: List[str], list of files to write the data to
    :param in_basedir: str, base directory of the read files,
                       to get partition date
    :param outfolder: str, the outgoing folder to write the data to
    :param partition_cols: List[str], partition columns
    :param state: SqCoalesceState, coalescer state, for constructing filename
    :param block_start: dateime, starting time window of this coalescing block
    :param block_end: dateime, ending time window of this coalescing block
    :returns: Nothing
    """
    if not filelist and not state.schema.type == "record":
        return

    state.block_start = int(block_start.timestamp())
    state.block_end = int(block_end.timestamp())
    if filelist:
        files_pervers = defaultdict(list)
        for file in filelist:
            sqversmatch = re.search(r'sqvers=([0-9]+\.[0-9]+)', file)
            if sqversmatch:
                files_pervers[sqversmatch.group(0)].append(file)

        this_df = pd.DataFrame()
        for files in files_pervers.values():
            tmp_df = ds.dataset(files, partitioning='hive',
                                partition_base_dir=in_basedir) \
                .to_table() \
                .to_pandas()
            if not tmp_df.empty:
                # Migrate each of the Dataframe before merging them
                # if necessary
                tmp_df = migrate_df(table, tmp_df, state.schema)
                this_df = pd.concat([this_df, tmp_df])

        state.wrrec_count += this_df.shape[0]

        if state.schema.type == "record":
            if not state.current_df.empty:
                this_df = this_df.set_index(state.keys)
                sett = set(this_df.index)
                setc = set(state.current_df.index)
                missing_set = setc.difference(sett)
                if missing_set:
                    missing_df = state.current_df.loc[missing_set]
                    this_df = pd.concat([this_df.reset_index(),
                                         missing_df.reset_index()])
                else:
                    this_df = this_df.reset_index()
    elif not state.current_df.empty:
        this_df = state.current_df.reset_index()
    else:
        return

    this_df.sqvers = state.schema.version  # Updating the schema version
    state.dbeng.write(state.table_name, "pandas", this_df, True,
                      state.schema.get_arrow_schema(),
                      state.pq_file_name)

    if state.schema.type == "record" and filelist:
        # Now replace the old dataframe with this new set for "record" types
        # Non-record types should never have current_df non-empty
        state.current_df = this_df.set_index(state.keys) \
                                  .drop(columns=['index'], errors='ignore') \
                                  .sort_values(by='timestamp') \
                                  .query('~index.duplicated(keep="last")')


def get_file_timestamps(filelist: List[str]) -> pd.DataFrame:
    """Read the files and construct a dataframe of files and timestamp of
       record in them.

    :param filelist: list, of full path name files, typically from pyarrow's
                     dataset.files
    :returns: dataframe of filename with the time it represents, sorted
    :rtype: pandas.DataFrame

    """
    if not filelist:
        return pd.DataFrame(columns=['file', 'timestamp'])

    # We can't rely on the system istat time to find the times involved
    # So read the data for each block and check. We tried using threading
    # and it didn't dramatically alter the results. Given that we might've
    # too many threads running with the poller and everything, we skipped
    # doing it.
    fname_list = []
    fts_list = []
    for file in filelist:
        try:
            ts = pd.read_parquet(file, columns=['timestamp'])
            fts_list.append(ts.timestamp.min())
            fname_list.append(file)
        except pa.ArrowInvalid:
            # skip this file because it can't be read, is probably 0 bytes
            logging.debug(f"not reading timestamp for {file}")
            # We would like to move the broken files to a separate directory
            # where we can perform additional investigations
            move_broken_file(file)

    # Construct file dataframe as its simpler to deal with
    if fname_list:
        fdf = pd.DataFrame({'file': fname_list, 'timestamp': fts_list})
        fdf['timestamp'] = humanize_timestamp(fdf.timestamp, 'UTC')
        return fdf.sort_values(by=['timestamp'])

    return pd.DataFrame(['file', 'timestamp'])


def migrate_df(table_name: str, df: pd.DataFrame,
               schema: SchemaForTable) -> pd.DataFrame:
    """Migrate the dataframe if necessary

    :param table_name: str, Name of the table
    :param df: pd.DataFrame, the dataframe to be migrated
    :param schema: SchemaForTable, the schema we're migrating to
    :returns: the migrated dataframe
    :rtype: pd.DataFrame
    """
    sqvers_list = df.sqvers.unique().tolist()
    do_migration = False
    for sqvers in sqvers_list:
        if sqvers != schema.version:
            do_migration = True
            migrate_fn = get_migrate_fn(table_name, sqvers,
                                        schema.version)
            if migrate_fn:
                df = migrate_fn(df, table_name, schema)

    if do_migration:
        df = generic_migration(df, table_name, schema)

    return df


def get_last_update_df(table_name: str, outfolder: str,
                       state: SqCoalesceState) -> pd.DataFrame:
    """Return a dataframe with the last known values for all keys
    The dataframe is sorted by timestamp and the index set to the keys. Works
    across namespaces.

    This is used when the coalesceer starts up and doesn't have any state
    about a table.

    :param table_name: str, name of the table we're getting data for
    :param outfolder: str, folder from where to gather the files
    :param state: SqCoalesceState, coalesceer state
    :returns: dataframe with the last known data for all hosts in namespace
    :rtype: pandas.DataFrame

    """
    dataset = ds.dataset(outfolder, partitioning='hive', format='parquet')
    files = sorted([x for x, y in zip(dataset.files, repeat(state.prefix))
                    if os.path.basename(x).startswith(y)])

    if not files:
        return pd.DataFrame()
    latest_filedict = {x.split('namespace=')[1].split('/')[0]: x
                       for x in files}

    latest_files = list(latest_filedict.values())
    current_df = ds.dataset(source=latest_files, partitioning='hive',
                            format='parquet') \
        .to_table() \
        .to_pandas(self_destruct=True)
    if not current_df.empty:
        # The data here could be old, so we need to migrate it first.
        current_df = migrate_df(table_name, current_df, state.schema)
        current_df = current_df.sort_values(by=['timestamp']) \
                               .set_index(state.keys)

    return current_df


def coalesce_resource_table(infolder: str, outfolder: str, archive_folder: str,
                            table: str, state: SqCoalesceState) -> None:
    """This routine coalesces all the parquet data in the folder provided

    This function MUST be called with sqPoller as the table the first time to
    build the polling period sample. Without this, its not possible to compute
    the records to be written for a period accurately. The polling periods are
    computed when this function is called the first time with None as the
    state field. This function stuffs the sqPoller timeblocks as the polling
    period in the state block and returns it. The state object returned also
    has some statistics written such as number of files written, number of
    records written and so on.

    :param infolder: str, folder to read data in from
    :param outfolder: str, folder to write data to
    :param archive_folder: str, folder to store the archived files in
    :param table: str, name of table we're coalesceing
    :param state: SqCoalesceState, state about this coalesceion run
    :returns: Nothing
    """

    def compute_block_start(start):
        return (start - timedelta(seconds=start.timestamp() %
                                  state.period.total_seconds()))

    partition_cols = ['sqvers', 'namespace']
    dodel = True

    state.wrfile_count = 0
    state.wrrec_count = 0
    state.table_name = table
    schema = state.schema

    if state.schema.type == "record":
        state.keys = schema.key_fields()
        if state.current_df.empty:
            state.current_df = get_last_update_df(table, outfolder, state)

    # Providing the schema, we don't perform any IO to read it, moreover,
    # we don't need to handle the case in which one of the files is broken.
    # We will detect them later.
    dataset = ds.dataset(infolder, partitioning='hive', format='parquet',
                         # Ignore reading the compressed files
                         ignore_prefixes=state.ign_pfx,
                         schema=schema.get_arrow_schema())

    state.logger.info(f'Examining {len(dataset.files)} {table} files '
                      f'for coalescing')
    fdf = get_file_timestamps(dataset.files)

    if fdf.empty:
        state.logger.info(f'No updates for {table} to coalesce')
        return

    start = fdf.timestamp.iloc[0]
    utcnow = datetime.now(timezone.utc)

    # We now need to determine if we're coalesceing a lot of data, at the start
    # or if we're only coalesceing for the last interval.
    if (utcnow < start):
        logging.error(
            'ERROR: Something is off, now is earlier than dates on files')
        return

    # We write data in fixed size time blocks. Data from 10 pm to 11 pm with a
    # period of 1 hour is written out as one block, data from 11-12 as another
    # and so on. Specifically, we write out 10:00:00 to 10:59:59 in the block
    block_start = compute_block_start(start)
    block_end = block_start + state.period

    # NOTE: You need the parentheses around the date comparison for some reason
    if (block_end > utcnow):
        return

    readblock = []
    wrfile_count = 0

    for row in fdf.itertuples():
        if block_start <= row.timestamp < block_end:
            readblock.append(row.file)
            continue

        # Write data if there are changes in the current time window
        if readblock:
            write_files(table, readblock, infolder, outfolder, partition_cols,
                        state, block_start, block_end)
            wrfile_count += len(readblock)

            # Archive the saved files. When this option is enable, it allows
            # us to restore the coalesced file, if something goes wrong with
            # the coalescer.
            archive_coalesced_files(readblock, archive_folder, state, dodel)

        # We need now to reset the time window according to the current file
        # timestamp
        readblock = []
        block_start = compute_block_start(row.timestamp)
        block_end = block_start + state.period

        # When the current timestamp is inside the new coalescing time windows
        # we have to stop
        if block_end > utcnow:
            break
        readblock = [row.file]

    # The last batch that ended before the block end
    if readblock:
        write_files(table, readblock, infolder, outfolder, partition_cols,
                    state, block_start, block_end)
        wrfile_count += len(readblock)
        archive_coalesced_files(readblock, archive_folder, state, dodel)

    state.wrfile_count = wrfile_count
    return
