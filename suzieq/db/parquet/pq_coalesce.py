import os
from datetime import datetime, timedelta, timezone
import logging
from typing import List
from itertools import repeat
import tarfile

import pandas as pd
import pyarrow.parquet as pq
import pyarrow.dataset as ds    # put this later due to some numpy dependency

from suzieq.shared.utils import humanize_timestamp
from suzieq.shared.schema import SchemaForTable
from suzieq.db.parquet.migratedb import get_migrate_fn


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
        self.poller_periods = set()
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
        this_df = ds.dataset(source=filelist, partitioning='hive',
                             partition_base_dir=in_basedir) \
            .to_table() \
            .to_pandas()
        state.wrrec_count += this_df.shape[0]

        if not this_df.empty:
            this_df = migrate_df(table, this_df, state.schema)

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


def find_broken_files(parent_dir: str) -> List[str]:
    """Find any files in the parent_dir that pyarrow can't read
    :parame parent_dir: str, the parent directory to investigate
    :returns: list of broken files
    :rtype: list of strings
    """

    all_files = []
    broken_files = []
    ro, _ = os.path.split(parent_dir)
    for root, _, files in os.walk(parent_dir):
        if ('_archived' not in root and '.sq-coalescer.pid' not in files
                and len(files) > 0):
            path = root.replace(ro, '')
            all_files.extend(list(map(lambda x: f"{path}/{x}", files)))
    for file in all_files:
        try:
            pq.ParquetFile(f"{ro}/{file}")
        except pq.lib.ArrowInvalid:
            broken_files.append(file)

    return broken_files


def move_broken_files(parent_dir: str, state: SqCoalesceState,
                      out_dir: str = '_broken', ) -> None:
    """ move any files that cannot be read by pyarrow in parent dir
        to a safe directory to be investigated later
    :param parent_dir: str, the parent directory to investigate
    :param state: SqCoalesceState, needed for the logger
    :param out_dir: str, diretory to put the broken files in
    :returns: Nothing
    :rtype: None
    """

    broken_files = find_broken_files(parent_dir)
    ro, _ = os.path.split(parent_dir)

    for file in broken_files:
        src = f"{ro}/{file}"
        dst = f"{ro}/{out_dir}/{file}"

        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        state.logger.debug(f"moving broken file {src} to {dst}")
        os.replace(src, dst)


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
        except OSError:
            # skip this file because it can't be read, is probably 0 bytes
            logging.debug(f"not reading timestamp for {file}")

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
    for sqvers in sqvers_list:
        if sqvers != schema.version:
            migrate_fn = get_migrate_fn(table_name, sqvers,
                                        schema.version)
            if migrate_fn:
                df = migrate_fn(df)

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


# pylint: disable=too-many-statements
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

    if table == "sqPoller":
        wr_polling_period = True
        state.poller_periods = set()
    else:
        wr_polling_period = False
    state.wrfile_count = 0
    state.wrrec_count = 0
    state.table_name = table
    schema = state.schema

    if state.schema.type == "record":
        state.keys = schema.key_fields()
        if state.current_df.empty:
            state.current_df = get_last_update_df(table, outfolder, state)

    # Ignore reading the compressed files
    try:
        dataset = ds.dataset(infolder, partitioning='hive', format='parquet',
                             ignore_prefixes=state.ign_pfx)
    except OSError:
        move_broken_files(infolder, state=state)
        dataset = ds.dataset(infolder, partitioning='hive', format='parquet',
                             ignore_prefixes=state.ign_pfx)

    state.logger.info(f'Examining {len(dataset.files)} {table} files '
                      f'for coalescing')
    fdf = get_file_timestamps(dataset.files)
    if fdf.empty:
        if (table == 'sqPoller') or (not state.poller_periods):
            return

    # this is no longer true if we are skipping files that aren't readable
    # assert(len(dataset.files) == fdf.shape[0])
    polled_periods = sorted(state.poller_periods)
    if fdf.empty:
        state.logger.info(f'No updates for {table} to coalesce')
        start = polled_periods[0]
    else:
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

    # We may start coalescing when nothing has changed for some initial period.
    # We have to write out records for that period.
    if schema.type == "record":
        for interval in polled_periods:
            if not fdf.empty and (block_end < interval):
                break
            pre_block_start = compute_block_start(interval)
            pre_block_end = pre_block_start + state.period
            write_files(table, readblock, infolder, outfolder, partition_cols,
                        state, pre_block_start, pre_block_end)

    for row in fdf.itertuples():
        if block_start <= row.timestamp < block_end:
            readblock.append(row.file)
            continue

        # Write data if either there's data to be written (readblock isn't
        # empty) OR this table is a record type and poller was alive during
        # this period (state's poller period for this window isn't blank
        if readblock or ((schema.type == "record") and
                         block_start in state.poller_periods):

            write_files(table, readblock, infolder, outfolder, partition_cols,
                        state, block_start, block_end)
            wrfile_count += len(readblock)
        if wr_polling_period and readblock:
            state.poller_periods.add(block_start)
        # Archive the saved files
        if readblock:
            archive_coalesced_files(readblock, archive_folder, state, dodel)

        # We have to find the timeslot where this record fits
        block_start = block_end
        block_end = block_start + state.period
        readblock = []
        if schema.type != "record":
            # We can jump directly to the timestamp corresonding to this
            # row's timestamp
            block_start = compute_block_start(row.timestamp)
            block_end = block_start + state.period
            if (row.timestamp > block_end) or (block_end > utcnow):
                break
            readblock = [row.file]
            continue

        while row.timestamp > block_end:
            if block_start in state.poller_periods:
                write_files(table, readblock, infolder, outfolder,
                            partition_cols, state, block_start, block_end)
                # Nothing to archive here, and we're not counting coalesced
                # records since these are duplicates
            block_start = block_end
            block_end = block_start + state.period
        if block_end > utcnow:
            break
        readblock = [row.file]

    # The last batch that ended before the block end
    if readblock or (fdf.empty and (schema.type == "record") and
                     block_start in state.poller_periods):
        write_files(table, readblock, infolder, outfolder, partition_cols,
                    state, block_start, block_end)
        wrfile_count += len(readblock)
        if wr_polling_period:
            state.poller_periods.add(block_start)
        archive_coalesced_files(readblock, archive_folder, state, dodel)

    state.wrfile_count = wrfile_count
    return
