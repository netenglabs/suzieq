import os
import pandas as pd
import pyarrow.dataset as ds    # put this later due to some numpy dependency
import pyarrow as pa
from datetime import datetime, timedelta, timezone
import logging
from typing import List
import pyarrow.parquet as pq
import tarfile

from suzieq.utils import load_sq_config, Schema, SchemaForTable
from suzieq.utils import humanize_timestamp


class SqCompactState(object):
    '''Class that compacts parquet files'''

    def __init__(self):
        self.time = None
        self.current_df = pd.DataFrame()
        self.keys = None
        self.type = None
        self.schema = None
        self.period = timedelta(hours=1)       # 1 hour is the default
        self.prefix = 'sqc-h-'   # sqc == suzieq compacter, h - hourly compact
        self.ign_pfx = ['.', '_', 'sqc-']  # Prefixes to ignore for compacting
        self.wrfile_count = 0
        self.wrrec_count = 0
        self.poller_periods = set()

    def pq_file_name(self, *args):
        """Callback to create a filename that uses the timestamp of start
        of hour. This makes it easy for us to lookup data when we need to.

        :returns: parquet filename to write
        :rtype: str

        """
        # Using timestamp rather than date/time string to simplify reads
        return f'{self.prefix}{self.time}.parquet'


def archive_compacted_files(filelist: List[str], outfolder: str,
                            state: SqCompactState, dodel: bool) -> None:
    """Tars and removes the already compacted files

    :param filelist: List{str], list of files to be tarred and archived
    :param outfolder: str, folder name where the archive is to be stored
    :param state: SqCompactState, state of compacter
    :param dodel: bool, True if the compacted files must be deleted
    :returns: Nothing
    """
    if filelist:
        with tarfile.open(f'{outfolder}/_archive-{state.prefix}-{state.time}.tar.bz2',
                          'w:bz2') as f:
            for file in filelist:
                f.add(file)
    if dodel:
        for file in filelist:
            os.remove(file)


def write_files(filelist: List[str], in_basedir: str,
                outfolder: str, partition_cols: List[str],
                state: SqCompactState) -> None:
    """Write the data from the list of files out as a single compacted block

    We're fixing the compression in this function
    :param filelist: List[str], list of files to write the data to
    :param in_basedir: str, base directory of the read files,
                       to get partition date
    :param outfolder: str, the outgoing folder to write the data to
    :param partition_cols: List[str], partition columns
    :returns: Nothing
    """
    if not filelist and not state.type == "record":
        return

    if filelist:
        wrtbl = ds.dataset(source=filelist, partitioning='hive',
                           partition_base_dir=in_basedir) \
            .to_table()
        state.wrrec_count += wrtbl.num_rows

        if state.type == "record":
            this_df = wrtbl.to_pandas()

            if not state.current_df.empty:
                this_df.set_index(state.keys, inplace=True)
                sett = set(this_df.index)
                setc = set(state.current_df.index)
                missing_df = state.current_df.loc[setc.difference(sett)]
                if not missing_df.empty:
                    this_df = pd.concat(
                        [this_df.reset_index(), missing_df.reset_index()])
                else:
                    this_df.reset_index(inplace=True)

            wrtbl = pa.Table.from_pandas(this_df, schema=state.schema,
                                         preserve_index=False)
    elif not state.current_df.empty:
        assert(state.type == "record")
        wrtbl = pa.Table.from_pandas(state.current_df.reset_index(),
                                     schema=state.schema,
                                     preserve_index=False)
    else:
        return

    pq.write_to_dataset(
        wrtbl,
        root_path=outfolder,
        partition_cols=partition_cols,
        version="2.0",
        compression='ZSTD',
        partition_filename_cb=state.pq_file_name,
        row_group_size=100000,
    )
    if filelist:
        state.wrrec_count += wrtbl.num_rows

    if state.type == "record" and filelist:
        # Now replace the old dataframe with this new set for "record" types
        # Non-record types should never have current_df non-empty
        state.current_df = this_df.set_index(state.keys) \
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
        return pd.DataFrame(['file', 'timestamp'])

    # We can't rely on the system istat time to find the times involved
    # So read the data for each block and check. We tried using threading
    # and it didn't dramatically alter the results. Given that we might've
    # too many threads running with the poller and everything, we skipped
    # doing it.
    fname_list = []
    fts_list = []
    for file in filelist:
        ts = pd.read_parquet(file, columns=['timestamp'])
        if not ts.empty:
            fname_list.append(file)
            fts_list.append(ts.timestamp.min())

    # Construct file dataframe as its simpler to deal with
    if fname_list:
        fdf = pd.DataFrame({'file': fname_list, 'timestamp': fts_list})
        fdf['timestamp'] = humanize_timestamp(fdf.timestamp, 'UTC')
        return fdf.sort_values(by=['timestamp'])

    return pd.DataFrame(['file', 'timestamp'])


def get_last_update_df(outfolder: str, state: SqCompactState) -> pd.DataFrame:
    """Return a dataframe with the last known values for all keys
    The dataframe is sorted by timestamp and the index set to the keys.

    This is used when the compacter starts up and doesn't have any state
    about a table.

    :param outfolder: str, folder from where to gather the files
    :param state: SqCompactState, compacter state
    :returns: dataframe with the last known data for all hosts in namespace
    :rtype: pandas.DataFrame

    """
    dataset = ds.dataset(outfolder, partitioning='hive', format='parquet')
    files = sorted([x for x in dataset.files if x.startswith(state.prefix)])
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
        current_df.timestamp = humanize_timestamp(current_df.timestamp)
        current_df.sort_values(by=['timetamp'], inplace=True)
        current_df.set_index(state.keys, inplace=True)

    return current_df


def compact_resource_table(infolder: str, outfolder: str, archive_folder: str,
                           table: str, schema: SchemaForTable,
                           state: SqCompactState) -> None:
    """This routine compacts all the parquet data in the folder provided

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
    :param table: str, name of table we're compacting
    :param tbl_schema: SchemaForTable, schema of table we're compacting
    :param state: SqCompactState, state about this compaction run
    :returns: Nothing
    """

    def compute_block_start(start):
        if state.period.total_seconds() < 24*3600:
            block_start = datetime(year=start.year, month=start.month,
                                   day=start.day, hour=start.hour,
                                   tzinfo=timezone.utc)
        elif 24*3600 <= state.period.total_seconds() < 24*3600*30:
            block_start = datetime(year=start.year, month=start.month,
                                   day=start.day, tzinfo=timezone.utc)
        elif 24*3600*30 <= state.period.total_seconds() < 24*3600*365:
            block_start = datetime(year=start.year, month=start.month,
                                   tzinfo=timezone.utc)
        else:
            block_start = datetime(year=start.year, tzinfo=timezone.utc)
        return block_start

    partition_cols = ['sqvers', 'namespace']
    dodel = False

    if table == "sqPoller":
        wr_polling_period = True
        state.poller_periods = set()
    else:
        wr_polling_period = False
    state.wrfile_count = 0
    state.wrrec_count = 0

    if schema.type == "record":
        state.keys = schema.key_fields()
        state.current_df = get_last_update_df(outfolder, state)
        state.type = schema.type
        state.schema = schema.get_arrow_schema()

    # Ignore reading the compressed files
    dataset = ds.dataset(infolder, partitioning='hive', format='parquet',
                         ignore_prefixes=state.ign_pfx)

    print(f'Files to compact: {len(dataset.files)}')
    fdf = get_file_timestamps(dataset.files)
    if fdf.empty and table == 'sqPoller':
        return

    assert(len(dataset.files) == fdf.shape[0])
    start = fdf.timestamp.iloc[0]
    utcnow = datetime.now(timezone.utc)

    # We now need to determine if we're compacting a lot of data, at the start
    # or if we're only compacting for the last interval.
    if (utcnow < start):
        logging.error(
            'ERROR: Something is off, now is earlier than dates on files')
        return

    # NOTE: You need the parentheses around the date comparison for some reason
    if start + state.period > utcnow:
        return

    # We write data in fixed size 1 hour time blocks. Data from 10-11 is
    # written out as one block, data from 11-12 as another and so on.
    # Specifically, we write out 11:00:00 to 11:59:59 in the block
    block_start = compute_block_start(start)
    block_end = block_start + state.period

    readblock = []
    wrfile_count = 0
    for row in fdf.itertuples():
        if block_start <= row.timestamp < block_end:
            readblock.append(row.file)
            continue

        # Write data if either there's data to be written (readblock isn't
        # empty) OR this table is a record type and poller was alive during
        # this period (state's poller period for this window isn't blank
        if readblock or ((state.type == "record") and
                         block_start in state.poller_periods):
            state.time = int(block_start.timestamp())
            write_files(readblock, infolder, outfolder, partition_cols, state)
            wrfile_count += len(readblock)
        if wr_polling_period and readblock:
            state.poller_periods.add(block_start)
        # Archive the saved files
        if readblock:
            archive_compacted_files(readblock, archive_folder, state, dodel)

        # We have to find the timeslot where this record fits
        block_start = block_end
        block_end = block_start + state.period
        if state.type != "record":
            # We can jump directly to the timestamp corresonding to this
            # row's timestamp
            if row.timestamp > block_end:
                block_start = compute_block_start(row.timestamp)
                block_end = block_start + state.period
                readblock = [row.file]
                continue

        readblock = []
        while row.timestamp > block_end:
            if block_start in state.poller_periods:
                state.time = int(block_start.timestamp())
                write_files(readblock, infolder, outfolder, partition_cols,
                            state)
            block_start = block_end
            block_end = block_start + state.period
        readblock = [row.file]
        if block_end > utcnow:
            break

    # The last batch that ended before the block end
    if readblock:
        state.time = int(block_start.timestamp())
        write_files(readblock, infolder, outfolder, partition_cols, state)
        wrfile_count += len(readblock)
        if wr_polling_period:
            state.poller_periods.add(block_start)
        archive_compacted_files(readblock, archive_folder, state, dodel)

    assert(wrfile_count == len(dataset.files))
    state.wrfile_count = wrfile_count
    return


def compact_resource_tables(cfg_file: str, table: str = None) -> None:
    """Compact all the resource parquet files in specified folder.


    :param infolder: str, root folder to check for resources
    :param outfolder: str, root folder for compacted record writes
    :param schemas: Schema, schemas used by the various resources
    :param period: str, period of compaction, 1h, 2h, 1w, 1d, 1m, 1y etc.
                   format is a number followed by one of [h, d, w]
                   for hour, day, week, month and year.
    :param table: str, optional, name of single table to compact
    :returns: Nothing
    """

    if not cfg_file:
        raise AttributeError('Suzieq config file must be specified')

    cfg = load_sq_config(config_file = cfg_file)
    if not cfg:
        raise AttributeError(f'Invalid Suzieq config file {cfg_file}')

    infolder = cfg['data-directory']
    outfolder = cfg.get('compact-directory', f'{infolder}/compacted')
    archive_folder = cfg.get('archive-directory', f'{infolder}/_archived')
    period = cfg.get('compacter', {'period': '1h'}).get('period', '1h')
    schemas = Schema(cfg.get('schema-directory'))

    state = SqCompactState()
    # Trying to be complete here. the ignore prefixes assumes you have compacters
    # across multiple time periods running, and so we need to ignore the files
    # created by the longer time period compactions. In other words, weekly
    # compacter should ignore monthly and yearly compacted files, monthly
    # compacter should ignore yearly compacter and so on.
    try:
        timeint = int(period[:-1])
        time_unit = period[-1]
        if time_unit == 'h':
            run_int = timedelta(hours=timeint)
            state.prefix = 'sqc-h-'
            state.ign_pfx = ['.', '_', 'sqc-']
        elif time_unit == 'd':
            run_int = timedelta(days=timeint)
            if timeint > 364:
                state.prefix = 'sqc-y-'
                state.ign_pfx = ['.', '_', 'sqc-y-']
            elif timeint > 29:
                state.prefix = 'sqc-m-'
                state.ign_pfx = ['.', '_', 'sqc-m-', 'sqc-y-']
            else:
                state.prefix = 'sqc-d-'
                state.ign_pfx = ['.', '_', 'sqc-d-', 'sqc-w-', 'sqc-m-',
                                 'sqc-y-']
        elif time_unit == 'w':
            run_int = timedelta(weeks=timeint)
            state.prefix = 'sqc-w-'
            state.ign_pfx = ['.', '_', 'sqc-w-', 'sqc-m-', 'sqc-y-']
        else:
            logging.error(f'Invalid unit for period, {time_unit}, '
                          'must be one of h/d/w')
    except ValueError:
        logging.error(f'Invalid time, {period}')
        return

    state.period = run_int
    # Create list of tables to compact
    tables = [x for x in schemas.tables()
              if schemas.type_for_table(x) != "derivedRecord"]
    if 'sqPoller' not in tables:
        # This is an error. sqPoller is how we keep track of discontinuities
        # among other things.
        print('No sqPoller data, cannot compute discontinuities')
        return
    else:
        tables.remove('sqPoller')
        tables.insert(0, 'sqPoller')
    if table and table not in tables:
        print('No info about table {table} to compact')
        return
    elif table:
        tables = ["sqPoller", table]

    # We've forced the sqPoller to be always the first table to be compacted
    for entry in tables:
        table_outfolder = f'{outfolder}/{entry}'
        table_infolder = f'{infolder}//{entry}'
        table_archive_folder = f'{archive_folder}/{entry}'
        if not os.path.isdir(table_infolder):
            print(f'No input records to compact for {entry}')
            continue
        if not os.path.isdir(table_outfolder):
            os.makedirs(table_outfolder)
        if not os.path.isdir(table_archive_folder):
            os.makedirs(table_archive_folder, exist_ok=True)
        compact_resource_table(table_infolder, table_outfolder,
                               table_archive_folder, entry,
                               SchemaForTable(entry, schemas, None),
                               state)
        print(f'compacted {state.wrfile_count} files/{state.wrrec_count} '
              f'of {entry}')
    return


if __name__ == '__main__':
    import sys
    import time

    print('USAGE: compact.py [table] [cfg-file]')

    if len(sys.argv) == 2:
        table = sys.argv[1]
    else:
        table = None

    if len(sys.argv) == 3:
        cfg_file = sys.argv[2]
    else:
        cfg_file = '~/.suzieq/suzieq-cfg.yml'

    exec_start = time.time()
    compact_resource_tables(cfg_file, table)
    exec_end = time.time()
    print(
        f'Compacted records in {timedelta(seconds=exec_end-exec_start)}')
