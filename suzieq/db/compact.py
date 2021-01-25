import os
import pandas as pd
import pyarrow.dataset as ds    # put this later due to some numpy dependency
import pyarrow as pa
from datetime import datetime, timedelta
import logging
from typing import List
import pyarrow.parquet as pq

from suzieq.utils import load_sq_config, Schema, SchemaForTable


class SqCompactState(object):
    '''Class to store state and provide support for compacting parwuet'''

    def __init__(self):
        self.time = None
        self.current_df = pd.DataFrame()
        self.keys = None
        self.type = None
        self.schema = None
        self.prefix = 'sqc-h'        # sqc == suzieq compacter, h - hourly compact
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
        return f'{self.prefix}-{self.time}.parquet'


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
        assert(state.type != "record")
        wrtbl = pa.Table.from_pandas(state.current_df, schema=state.schema,
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
    fdata = {}
    for file in filelist:
        ts = pd.read_parquet(file, columns=['timestamp'])
        if not ts.empty:
            fdata[file] = ts.timestamp.min()

    # Construct file dataframe as its simpler to deal with
    if fdata:
        fdf = pd.DataFrame({'file': fdata.keys(), 'timestamp': fdata.values()})
        fdf['timestamp'] = pd.to_datetime(fdf.timestamp, unit='ms')
        return fdf.sort_values(by=['timestamp'])

    return pd.DataFrame(['file', 'timestamp'])


def get_last_update_df(outfolder: str, keys: List[str]) -> pd.DataFrame:
    """Return a dataframe with the last known values for all keys
    The dataframe is sorted by timestamp and the index set to the keys.

    :param outfolder: str, folder from where to gather the files
    :param keys: List[str], list of key fields
    :returns: dataframe with the last known data for all hosts in namespace
    :rtype: pandas.DataFrame

    """
    dataset = ds.dataset(outfolder, partitioning='hive', format='parquet')
    files = sorted([x for x in dataset.files if x.startswith('sfc-')])
    if not files:
        return pd.DataFrame()
    latest_filedict = {(x.split('namespace=')[1].split('/')[0],
                        x.split('namespace=')[1].split('/')[1]
                        .split('hostname=')[1].split('/')[0]): x for x in files}

    latest_files = list(latest_filedict.values())
    current_df = ds.dataset(source=latest_files, partitioning='hive',
                            format='parquet') \
        .to_table() \
        .to_pandas(self_destruct=True)
    if not current_df.empty:
        current_df.timestamp = pd.to_datetime(current_df.timestamp, unit='ms')
        current_df.sort_values(by=['timetamp'], inplace=True)
        current_df.set_index(keys, inplace=True)

    return current_df


def compact_resource_table(infolder: str, outfolder: str,
                           table: str, schema: SchemaForTable,
                           state: SqCompactState) -> SqCompactState:
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
    :param table: str, name of table we're compacting
    :param tbl_schema: SchemaForTable, schema of table we're compacting
    :param state: SqCompactState, None or state returned from prev table
    :returns: state of compaction needed for non-sqPollers, has stats etc.
    """

    if not state:
        state = SqCompactState()  # save the timestamp for use as the filename
        wr_polling_period = True
    else:
        wr_polling_period = False
    state.wrfile_count = 0
    state.wrrec_count = 0

    if schema.type == "record":
        state.keys = schema.key_fields()
        state.current_df = get_last_update_df(outfolder, state.keys)
        state.type = schema.type
        state.schema = schema.get_arrow_schema()

    # Ignore reading the compressed files
    dataset = ds.dataset(infolder, partitioning='hive', format='parquet',
                         ignore_prefixes=['.', '_', 'sfc-'])

    print(f'Files to compact: {len(dataset.files)}')
    fdf = get_file_timestamps(dataset.files)
    if fdf.empty and table == 'sqPoller':
        return None

    assert(len(dataset.files) == fdf.shape[0])
    start = fdf.timestamp.iloc[0]
    utcnow = datetime.utcnow()     # All times we store are UTC based

    # We now need to determine if we're compacting a lot of data, at the start
    # or if we're only compacting for the last interval.
    if (utcnow < start):
        logging.error(
            'ERROR: Something is off, now is earlier than dates on files')
        return

    # NOTE: You need the parentheses around the date comparison for some reason
    if (utcnow.date() != start.date()):
        hr_start = start.hour
    elif utcnow.hour == start.hour:
        hr_start = None
    else:
        hr_start = start.hour

    if not hr_start:
        # If we've been woken up before the current hour is up, don't do
        # anything. We'll be woken up again
        return state

    # We write data in fixed size 1 hour time blocks. Data from 10-11 is
    # written out as one block, data from 11-12 as another and so on.
    # Specifically, we write out 11:00:00 to 11:59:59 in the block
    block_start = datetime(year=start.year, month=start.month,
                           day=start.day, hour=hr_start)
    block_end = block_start + timedelta(hours=1)

    readblock = []
    wrfile_count = 0
    for row in fdf.itertuples():
        if block_start <= row.timestamp < block_end:
            readblock.append(row.file)
            continue

        if readblock or (not wr_polling_period and (state.type == "record")
                         and block_start in state.poller_periods):
            state.time = int(block_start.timestamp())
            write_files(readblock, infolder, outfolder,
                        ['sqvers', 'namespace', 'hostname'], state)
            wrfile_count += len(readblock)
        if wr_polling_period and readblock:
            state.poller_periods.add(block_start)
        readblock = [row.file]
        block_start = block_end
        block_end = block_start + timedelta(hours=1)
        if block_end > utcnow:
            break

    # The last batch that ended before the block end
    if readblock:
        state.time = int(block_start.timestamp())
        write_files(readblock, infolder, outfolder,
                    ['sqvers', 'namespace', 'hostname'], state)
        wrfile_count += len(readblock)

    assert(wrfile_count == len(dataset.files))
    state.wrfile_count = wrfile_count
    return state


def compact_resource_tables(infolder: str, outfolder: str,
                            schemas: dict, table: str = None) -> None:
    """Compact all the resource tables necessary

    :param infolder: str, root folder to check for resources
    :param outfolder: str, root folder for compacted record writes
    :param schemas: Schema, schemas used by the various resources
    :param table: str, optional, name of single table to compact
    :returns: Nothing
    """

    # Create list of tables to compact
    tables = [x for x in schemas.tables()
              if schemas.type_for_table(x) != "derivedRecord"]
    if 'sqPoller' not in tables:
        # This is an error. sqPoller is how we keep track of discontinuities
        # among other things.
        print('No sqPoller data, cannot compute discontinuities')
        return
    if table not in tables:
        print('No info about table {table} to compact')
        return
    elif table:
        tables = [table]

    # Need to compute the polling period
    table_outfolder = f'{outfolder}//sqPoller'
    table_infolder = f'{infolder}//sqPoller'
    if not os.path.isdir(table_infolder):
        print('No sqpoller info. Aborting')
        return
    if not os.path.isdir(table_outfolder):
        os.mkdir(table_outfolder)
    state = compact_resource_table(table_infolder, table_outfolder, 'sqPoller',
                                   SchemaForTable('sqPoller', schemas, None),
                                   None)

    for entry in tables:
        table_outfolder = f'{outfolder}/{table}'
        table_infolder = f'{infolder}//{table}'
        if not os.path.isdir(table_infolder):
            print(f'No input records to compact for {table}')
            continue
        if not os.path.isdir(table_outfolder):
            os.mkdir(table_outfolder)
        state = compact_resource_table(table_infolder, table_outfolder, entry,
                                       SchemaForTable(entry, schemas, None),
                                       state)
        print(f'compacted {state.wrfile_count} files/{state.wrrec_count} '
              f'of {table}')
    return


if __name__ == '__main__':
    import sys
    import time

    if len(sys.argv) < 3:
        print(
            'USAGE: compact.py <in_folder> <out_folder> [[table] [cfg-file]]')
        sys.exit(1)

    if len(sys.argv) == 4:
        table = sys.argv[3]
    else:
        table = None

    if not os.path.isdir(sys.argv[1]):
        print(f'ERROR: Input folder {sys.argv[1]} not a directory')
        sys.exit(1)
    if not os.path.isdir(sys.argv[2]):
        print(f'ERROR: Output folder {sys.argv[2]} not a directory')
        sys.exit(1)

    if len(sys.argv) > 4:
        cfg_file = sys.argv[4]
    else:
        cfg_file = '~/.suzieq/suzieq-cfg.yml'

    cfg = load_sq_config(cfg_file)
    if cfg:
        schemas = Schema(cfg['schema-directory'])

    exec_start = time.time()
    compact_resource_tables(
        sys.argv[1], sys.argv[2], schemas, table)
    exec_end = time.time()
    print(
        f'Compacted records in {timedelta(seconds=exec_end-exec_start)}')
