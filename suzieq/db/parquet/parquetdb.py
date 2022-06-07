import os
import re
from time import time
from typing import List, Optional
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from contextlib import suppress
from shutil import rmtree
from collections import defaultdict

import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from suzieq.db.base_db import SqDB, SqCoalesceStats
from suzieq.shared.schema import Schema, SchemaForTable

from suzieq.db.parquet.pq_coalesce import (SqCoalesceState,
                                           coalesce_resource_table)
from suzieq.db.parquet.migratedb import get_migrate_fn


class SqParquetDB(SqDB):
    '''Class supporting Parquet backend as DB'''

    def __init__(self, cfg: dict, logger: logging.Logger) -> None:
        '''Init the Parquet DB object'''
        self.cfg = cfg
        self.logger = logger or logging.getLogger()

    def supported_data_formats(self):
        '''What formats are supported as return types by DB'''
        return ['pandas']

    def get_tables(self):
        """Return list of tables known to parquet
        """
        folder = self._get_table_directory(None, False)
        dirs = Path(folder).glob('*')
        tables = [str(x.stem) for x in dirs
                  if not str(x.stem).startswith(('_', 'coalesced'))]

        return tables

    # pylint: disable=too-many-statements
    def read(self, table_name: str, data_format: str,
             **kwargs) -> pd.DataFrame:
        """Read the data specified from parquet files and return

        This function also implements predicate pushdown to filter the data
        as specified by the provided filters.

        :param table_name: str, the name of the table to be read
        :param data_format: str, Format the data's to be returned in,
                            (only pandas supported at this point)
        :param columns: List[str], list of columns requested to be read,
                        only those specified are returned, keyword arg
        :param key_fields: List[str], key fields for table, required to
                           deduplicate, keyword arg only
        :param view: str, one of ["latest", "all"], keyword arg only
        :param start: float, starting time window for data, timestamp,
                      can be 0 to indicate latest, keyword arg only
        :param end: float, ending time window for data, timestamp,
                    can be 0 to indicate latest, keyword arg only,
        :param kwargs: dict, the optional keyword arguments, addnl_filter,
                       and merge_fields, not needed typically
        :returns: pandas dataframe of the data specified, or None if
                  unsupported format
        :rtype: pd.DataFrame

        """

        if data_format not in self.supported_data_formats():
            return None

        start = kwargs.pop("start_time")
        end = kwargs.pop("end_time")
        view = kwargs.pop("view")
        fields = kwargs.pop("columns")
        key_fields = kwargs.pop("key_fields")
        addnl_filter = kwargs.pop("add_filter", None)
        merge_fields = kwargs.pop('merge_fields', {})
        _ = kwargs.pop('hostname', [])  # This should never be passed
        namespace = kwargs.pop('namespace', [])

        folder = self._get_table_directory(table_name, False)

        if not all(x in fields for x in key_fields):
            raise ValueError('Key fields MUST be included in columns list')

        if addnl_filter:
            # This is for special cases that are specific to an object
            query_str = addnl_filter
        else:
            query_str = None

        if query_str is None:
            # Make up a dummy query string to avoid if/then/else
            query_str = "timestamp != 0"

        # If sqvers is in the requested data, we've to handle it separately
        if 'sqvers' in fields:
            fields.remove('sqvers')
            need_sqvers = True
            max_vers = 0
        else:
            need_sqvers = False

        # If requesting a specific version of the data, handle that diff too
        sqvers = kwargs.pop('sqvers', None)
        final_df = pd.DataFrame()
        try:
            dirs = Path(folder)
            try:
                for elem in dirs.iterdir():
                    # Additional processing around sqvers filtering and data
                    if 'sqvers=' not in str(elem):
                        continue
                    if sqvers and f'sqvers={sqvers}' != elem:
                        continue
                    if need_sqvers:
                        vers = float(str(elem).split('=')[-1])
                        if vers > max_vers:
                            max_vers = vers

                    dataset = ds.dataset(elem, format='parquet',
                                         partitioning='hive')

                    if not dataset.files:
                        continue

                    tmp_df = self._process_dataset(dataset, namespace, start,
                                                   end, fields, merge_fields,
                                                   query_str, **kwargs)
                    if not tmp_df.empty:
                        final_df = pd.concat([final_df, tmp_df])
            except FileNotFoundError:
                pass
            except Exception as e:
                raise e

            # Now operate on the coalesced data set
            cp_dataset = self._get_cp_dataset(table_name, need_sqvers, sqvers,
                                              view, start, end)
            if cp_dataset:
                tmp_df = self._process_dataset(cp_dataset, namespace, start,
                                               end, fields, merge_fields,
                                               query_str, **kwargs)
                if not tmp_df.empty:
                    final_df = pd.concat([final_df, tmp_df])

            # Because of how coalescing works, we can have multiple duplicated
            # entries with same timestamp. Remove them
            if not final_df.empty:
                final_df = final_df.sort_values(by=['timestamp'])
                dupts_keys = key_fields + ['timestamp']
                final_df = final_df.set_index(dupts_keys) \
                    .query('~index.duplicated(keep="last")') \
                    .reset_index()
                if not final_df.empty and (view == 'latest'):
                    final_df = final_df.set_index(key_fields) \
                        .query('~index.duplicated(keep="last")')
        except (pa.lib.ArrowInvalid, OSError):
            return pd.DataFrame(columns=fields)

        if need_sqvers:
            final_df['sqvers'] = max_vers
            fields.insert(0, 'sqvers')

        cols = set(final_df.columns.tolist() + final_df.index.names)
        for fld in [x for x in fields if x not in cols]:
            final_df[fld] = ''
        return final_df.reset_index()[fields]

    def write(self, table_name: str, data_format: str,
              data, coalesced: bool, schema: pa.lib.Schema,
              filename_cb, **kwargs) -> int:
        """Write the data supplied as a dataframe as a parquet file

        :param cfg: Suzieq configuration
        :param table_name: str, Name of the table to write data to
        :param data: data to be written, usually pandas DF, but can be
                     engine specific (spark, dask etc.)
        :param data_format: str, Format the data's to be returned in,
                            (only pandas supported at this point)
        :param coalesced: bool, True if data being written is in compacted form
        :param schema: pa.Schema, the schema for the data
        :param filename_cb: callable, callback function to create the filename
        :returns: status of write
        :rtype: integer

        """
        folder = self._get_table_directory(table_name, coalesced)
        if coalesced:
            partition_cols = ['sqvers', 'namespace']
        else:
            partition_cols = ['sqvers', 'namespace', 'hostname']

        schema_def = dict(zip(schema.names, schema.types))
        defvals = self._get_default_vals()

        if data_format == "pandas":
            if isinstance(data, pd.DataFrame):
                cols = data.columns

                # Ensure all fields are present
                for field in schema_def:
                    if field not in cols:
                        data[field] = defvals.get(schema_def[field], '')

                table = pa.Table.from_pandas(data, schema=schema,
                                             preserve_index=False)
            elif isinstance(data, pa.Table):
                table = data
            elif isinstance(data, dict):
                df = pd.DataFrame.from_dict(data["records"])
                table = pa.Table.from_pandas(df, schema=schema,
                                             preserve_index=False)

            if filename_cb:
                pq.write_to_dataset(table, root_path=folder,
                                    partition_cols=partition_cols,
                                    version="2.0", compression="ZSTD",
                                    partition_filename_cb=filename_cb,
                                    row_group_size=100000)
            else:
                pq.write_to_dataset(table, root_path=folder,
                                    partition_cols=partition_cols,
                                    version="2.0", compression="ZSTD",
                                    row_group_size=100000)

        return 0

    # pylint: disable=too-many-statements
    def coalesce(self, tables: List[str] = None, period: str = '',
                 ign_sqpoller: bool = False) -> Optional[List]:
        """Coalesce all the resource parquet files in specified folder.

        This routine does not run periodically. It runs once and returns.

        :param tables: List[str], List of specific tables to coalesce,
                       empty for all
        :param period: str, coalescing period, needed for various internal
                       stuff
        :param ign_sqpoller: True if its OK to ignore the absence of sqpoller
                             to coalesce
        :returns: coalesce statistics list, one per table
        :rtype: SqCoalesceStats
        """

        infolder = self.cfg['data-directory']
        outfolder = self._get_table_directory('', True)  # root folder
        archive_folder = self.cfg.get('coalescer', {}) \
            .get('archive-directory',
                 f'{infolder}/_archived')

        if not period:
            period = self.cfg.get(
                'coalesceer', {'period': '1h'}).get('period', '1h')
        schemas = Schema(self.cfg.get('schema-directory'))
        state = SqCoalesceState(self.logger, period)

        state.logger = self.logger
        # Trying to be complete here. the ignore prefixes assumes you have
        # coalesceers across multiple time periods running, and so we need
        # to ignore the files created by the longer time period coalesceions.
        # In other words, weekly coalesceer should ignore monthly and yearly
        # coalesced files, monthly coalesceer should ignore yearly coalesceer
        # and so on.
        try:
            timeint = int(period[:-1])
            time_unit = period[-1]
            if time_unit == 'm':
                run_int = timedelta(minutes=timeint)
                state.prefix = 'sqc-m-'
                state.ign_pfx = ['.', '_', 'sqc-']
            elif time_unit == 'h':
                run_int = timedelta(hours=timeint)
                state.prefix = 'sqc-h-'
                state.ign_pfx = ['.', '_', 'sqc-y-', 'sqc-d-', 'sqc-w-',
                                 'sqc-M-']
            elif time_unit == 'd':
                run_int = timedelta(days=timeint)
                if timeint > 364:
                    state.prefix = 'sqc-y-'
                    state.ign_pfx = ['.', '_', 'sqc-y-']
                elif timeint > 29:
                    state.prefix = 'sqc-M-'
                    state.ign_pfx = ['.', '_', 'sqc-M-', 'sqc-y-']
                else:
                    state.prefix = 'sqc-d-'
                    state.ign_pfx = ['.', '_', 'sqc-m-', 'sqc-d-', 'sqc-w-',
                                     'sqc-M-', 'sqc-y-']
            elif time_unit == 'w':
                run_int = timedelta(weeks=timeint)
                state.prefix = 'sqc-w-'
                state.ign_pfx = ['.', '_', 'sqc-w-', 'sqc-m-', 'sqc-y-']
            else:
                logging.error(f'Invalid unit for period, {time_unit}, '
                              'must be one of m/h/d/w')
        except ValueError:
            logging.error(f'Invalid time, {period}')
            return None

        state.period = run_int
        # Create list of tables to coalesce.
        # TODO: Verify that we're only coalescing parquet tables here
        if tables:
            tables = [x for x in tables
                      if schemas.tables() and
                      (schemas.type_for_table(x) != "derivedRecord")]
        else:
            tables = [x for x in schemas.tables()
                      if schemas.type_for_table(x) != "derivedRecord"]
        if 'sqPoller' not in tables and not ign_sqpoller:
            # This is an error. sqPoller keeps track of discontinuities
            # among other things.
            self.logger.error(
                'No sqPoller data, cannot compute discontinuities')
            return None
        else:
            # We want sqPoller to be first to compute discontinuities
            with suppress(ValueError):
                tables.remove('sqPoller')
            if not ign_sqpoller:
                tables.insert(0, 'sqPoller')

        # We've forced the sqPoller to be always the first table to coalesce
        stats = []
        for entry in tables:
            table_outfolder = f'{outfolder}/{entry}'
            table_infolder = f'{infolder}//{entry}'
            if archive_folder:
                table_archive_folder = f'{archive_folder}/{entry}'
            else:
                table_archive_folder = None
            state.current_df = pd.DataFrame()
            state.dbeng = self
            state.schema = SchemaForTable(entry, schemas, None)
            if not os.path.isdir(table_infolder):
                self.logger.info(
                    f'No input records to coalesce for {entry}')
                continue
            try:
                if not os.path.isdir(table_outfolder):
                    os.makedirs(table_outfolder)
                if (table_archive_folder and
                        not os.path.isdir(table_archive_folder)):
                    os.makedirs(table_archive_folder, exist_ok=True)
                # Migrate the data if needed
                self.logger.debug(f'Migrating data for {entry}')
                self.migrate(entry, state.schema)
                self.logger.debug(f'Migrating data for {entry}')
                start = time()
                coalesce_resource_table(table_infolder, table_outfolder,
                                        table_archive_folder, entry,
                                        state)
                end = time()
                self.logger.info(
                    f'coalesced {state.wrfile_count} '
                    f'files/{state.wrrec_count} '
                    f'records of {entry}')
                stats.append(SqCoalesceStats(entry, period, int(end-start),
                                             state.wrfile_count,
                                             state.wrrec_count,
                                             int(datetime.now(tz=timezone.utc)
                                                 .timestamp() * 1000)))
            except Exception:  # pylint: disable=broad-except
                self.logger.exception(f'Unable to coalesce table {entry}')
                stats.append(SqCoalesceStats(entry, period, int(end-start),
                                             0, 0,
                                             int(datetime.now(tz=timezone.utc)
                                                 .timestamp() * 1000)))

        return stats

    def migrate(self, table_name: str, schema: SchemaForTable) -> None:
        """Migrates the data for the table specified to latest version

        :param table_name: str, The name of the table to migrate
        :param schema: SchemaForTable, the current schema
        :returns: None
        :rtype:
        """

        current_vers = schema.version
        defvals = self._get_default_vals()
        arrow_schema = schema.get_arrow_schema()
        schema_def = dict(zip(arrow_schema.names, arrow_schema.types))

        # pylint: disable=too-many-nested-blocks
        for sqvers in self._get_avail_sqvers(table_name, True):
            if sqvers != current_vers:
                migrate_rtn = get_migrate_fn(table_name, sqvers, current_vers)
                if migrate_rtn:
                    dataset = self._get_cp_dataset(table_name, True, sqvers,
                                                   'all', '', '')
                    for item in dataset.files:
                        try:
                            namespace = item.split('namespace=')[1] \
                                .split('/')[0]
                        except IndexError:
                            # Don't convert data not in our template
                            continue

                        df = pd.read_parquet(item)
                        df['sqvers'] = sqvers
                        df['namespace'] = namespace
                        newdf = migrate_rtn(df)

                        cols = newdf.columns
                        # Ensure all fields are present
                        for field in schema_def:
                            if field not in cols:
                                newdf[field] = defvals.get(schema_def[field],
                                                           '')

                        newdf.drop(columns=['namespace', 'sqvers'])

                        newitem = item.replace(f'sqvers={sqvers}',
                                               f'sqvers={current_vers}')
                        newdir = os.path.dirname(newitem)
                        if not os.path.exists(newdir):
                            os.makedirs(newdir, exist_ok=True)

                        table = pa.Table.from_pandas(
                            newdf, schema=schema.get_arrow_schema(),
                            preserve_index=False)
                        pq.write_to_dataset(table, newitem,
                                            version="2.0", compression="ZSTD",
                                            row_group_size=100000)
                        self.logger.debug(
                            f'Migrated {item} version {sqvers}->'
                            f'{current_vers}')
                        os.remove(item)

                    rmtree(
                        f'{self._get_table_directory(table_name, True)}/'
                        f'sqvers={sqvers}', ignore_errors=True)

    def _get_avail_sqvers(self, table_name: str, coalesced: bool) -> List[str]:
        """Get list of DB versions for a given table.

        At this time it does not check if the DB is empty of not of these
        versions.

        :param table_name: str, name of table for which you want the versions
        :param coalesced: boolean, True if you want to look in coalesced dir
        :returns: list of DB versions
        :rtype: List[str]

        """

        folder = self._get_table_directory(table_name, coalesced)
        dirs = Path(folder)
        sqvers_list = []
        for folder in dirs.glob('sqvers=*'):
            with suppress(IndexError):
                sqvers = folder.name.split('sqvers=')[1]
                if sqvers:
                    sqvers_list.append(sqvers)

        return sqvers_list

    def _process_dataset(self, dataset: ds.Dataset, namespace: List[str],
                         start: str, end: str, fields: List[str],
                         merge_fields: List[str], query_str: str,
                         **kwargs) -> pd.DataFrame:
        '''Process provided dataset and return a pandas DF'''

        # Build the filters for predicate pushdown
        master_schema = dataset.schema

        avail_fields = [f for f in fields if f in master_schema.names]
        filters = self.build_ds_filters(
            start, end, master_schema, merge_fields=merge_fields,
            **kwargs)

        filtered_dataset = self._get_filtered_fileset(dataset, namespace)

        if not filtered_dataset.files:
            return pd.DataFrame()

        tmp_df = filtered_dataset \
            .to_table(filter=filters, columns=avail_fields) \
            .to_pandas(self_destruct=True) \
            .query(query_str)

        if merge_fields and not tmp_df.empty:
            # These are key fields that need to be set right before we do
            # the drop duplicates to avoid missing out all the data
            for field in merge_fields:
                newfld = merge_fields[field]
                if (field in tmp_df.columns and
                        newfld in tmp_df.columns):
                    tmp_df[newfld] = np.where(tmp_df[newfld],
                                              tmp_df[newfld],
                                              tmp_df[field])
                elif (field in tmp_df.columns and
                      newfld not in tmp_df.columns):
                    tmp_df = tmp_df.rename(columns={field: newfld})

        return tmp_df

    def _get_cp_dataset(self, table_name: str, need_sqvers: bool,
                        sqvers: str, view: str, start_time: float,
                        end_time: float) -> ds.dataset:
        """Get the list of files to read in coalesced dir

        This iterates over the coalesced files that need to be read and comes
        up with a list of files that corresponds to the timeslot the user has
        specified

        :param table_name: str, Table for which coalesced info is requested
        :param need_sqvers: bool, True if the user has requested that we
                            return the sqvers
        :param sqvers: str, if we're looking only for files of a specific vers
        :param view: str, whether to return the latest only OR all
        :param start_time: float, the starting time window of data needed
        : param end_time: float, the ending time window of data needed
        :returns: pyarrow dataset for the files to be read
        :rtype: pyarrow.dataset.dataset

        """

        filelist = []
        max_vers = 0

        folder = self._get_table_directory(table_name, True)

        # We need to iterate otherwise the differing schema from different dirs
        # causes the read to abort.
        dirs = Path(folder)
        if not dirs.exists() or not dirs.is_dir():
            return []

        # pylint: disable=too-many-nested-blocks
        for elem in dirs.iterdir():
            # Additional processing around sqvers filtering and data
            if 'sqvers=' not in str(elem):
                continue
            if sqvers and f'sqvers={sqvers}' != elem.name:
                continue
            if need_sqvers:
                vers = float(str(elem).split('=')[-1])
                if vers > max_vers:
                    max_vers = vers

            dataset = ds.dataset(elem, format='parquet', partitioning='hive')

            if view == "all" and not (start_time or end_time):
                selected_in_dir = dataset.files
            else:
                files_per_ns = defaultdict(list)
                for f in dataset.files:
                    nsp = os.path.dirname(f).split('namespace=')[-1]
                    files_per_ns[nsp].append(f)

                selected_in_dir = []
                for ele in files_per_ns:
                    # We've to account for the set from each namespace
                    selected_in_ns = []
                    files_per_ns[ele].sort()
                    if not start_time and not end_time:
                        selected_in_dir.append(files_per_ns[ele][-1])
                        continue

                    start_selected = False
                    for i, file in enumerate(files_per_ns[ele]):
                        thistime = os.path.basename(file).split('.')[0] \
                            .split('-')[-2:]
                        thistime = [int(x)*1000 for x in thistime]  # to msec
                        if (not start_time) or start_selected or (
                                thistime[0] <= start_time <= thistime[1]):
                            if not end_time:
                                selected_in_dir.extend(files_per_ns[ele][i:])
                                break
                            if thistime[0] <= end_time:
                                if (start_time or start_selected or
                                        view == "all"):
                                    selected_in_dir.append(file)
                                    start_selected = True
                                else:
                                    # When we're only operating on end-time,
                                    # we need at most 2 files as a specified
                                    # end time can at best straddle two files
                                    # because the time provided falls between
                                    # the end of one file and the end time of
                                    # the next file. That is what we're doing
                                    # here. As the coalescer keeps all the
                                    # the unique records, according to their
                                    # keys
                                    if len(selected_in_ns) > 1:
                                        selected_in_ns[0] = selected_in_ns[1]
                                        selected_in_ns[1] = file
                                    else:
                                        selected_in_ns.append(file)
                            else:
                                break
                    if selected_in_ns:
                        selected_in_dir.extend(selected_in_ns)
            if selected_in_dir:
                filelist.extend(selected_in_dir)

        if filelist:
            return ds.dataset(filelist, format='parquet', partitioning='hive')
        else:
            return []

    def _build_master_schema(self, datasets: list) -> pa.lib.Schema:
        """Build the master schema from the list of diff versions
        We use this to build the filters and use the right type-based check
        for a field.
        """
        msch = datasets[0].schema
        msch_set = set(msch)
        for dataset in datasets[1:]:
            sch = dataset.schema
            sch_set = set(sch)
            if msch_set.issuperset(sch):
                continue
            if sch_set.issuperset(msch):
                msch = sch
            else:
                for fld in sch_set-msch_set:
                    msch.append(fld)

        return msch

    def _get_filtered_fileset(self, dataset: ds, namespace: list) -> ds:
        """Filter the dataset based on the namespace

        We can use this method to filter out namespaces and hostnames based
        on regexes as well just regular strings.
        Args:
            datasets (list)): The datasets list incl coalesced and not files
            namespace (list): list of namespace strings

        Returns:
            ds: pyarrow dataset of only the files that match filter
        """
        if not namespace:
            return dataset

        # Exclude not and regexp operators as they're handled elsewhere.
        excluded_ns = [x for x in namespace
                       if x.startswith('!') or x.startswith('~!')]
        if excluded_ns != namespace:
            ns_filters = [x for x in namespace
                          if not x.startswith('!') and not x.startswith('~!')]
        else:
            ns_filters = namespace
        ns_filelist = []
        chklist = dataset.files
        for ns in ns_filters or []:
            if ns.startswith('!'):
                ns = ns[1:]
                ns_filelist = \
                    [x for x in chklist
                     if not re.search(f'namespace={ns}/', x)]
                chklist = ns_filelist
            elif ns.startswith('~'):
                ns = ns[1:]
                if ns.startswith('!'):
                    ns = ns[1:]
                    ns_filelist = \
                        [x for x in chklist
                         if not re.search(f'namespace={ns}/', x)]
                    chklist = ns_filelist
                else:
                    ns_filelist.extend(
                        [x for x in dataset.files
                         if re.search(f'namespace={ns}/', x)])
            else:
                ns_filelist.extend(
                    [x for x in dataset.files
                     if re.search(f'namespace={ns}/', x)])

        return ds.dataset(ns_filelist, format='parquet', partitioning='hive')

    def _cons_int_filter(self, keyfld: str, filter_str: str) -> ds.Expression:
        '''Construct Integer filters with arithmetic operations'''
        if not isinstance(filter_str, str):
            return (ds.field(keyfld) == int(filter_str))

        # Check if we have logical operator (<, >, = etc.)
        if filter_str.startswith('<='):
            return (ds.field(keyfld) <= int(filter_str[2:]))
        elif filter_str.startswith('>='):
            return (ds.field(keyfld) >= int(filter_str[2:]))
        elif filter_str.startswith('<'):
            return (ds.field(keyfld) < int(filter_str[1:]))
        elif filter_str.startswith('>'):
            return (ds.field(keyfld) > int(filter_str[1:]))
        else:
            return (ds.field(keyfld) == int(filter_str))

    # pylint: disable=too-many-statements
    def build_ds_filters(self, start_tm: float, end_tm: float,
                         schema: pa.lib.Schema,
                         **kwargs) -> ds.Expression:
        """The new style of filters using dataset instead of ParquetDataset"""

        merge_fields = kwargs.pop('merge_fields', {})
        # The time filters first
        if start_tm and not end_tm:
            filters = ds.field("timestamp") >= start_tm
        elif end_tm and not start_tm:
            filters = ds.field("timestamp") <= end_tm
        elif start_tm and end_tm:
            filters = ((ds.field("timestamp") >= start_tm)
                       & (ds.field("timestamp") <= end_tm))
        else:
            filters = (ds.field("timestamp") != 0)

        sch_fields = schema.names
        # pylint: disable=too-many-nested-blocks
        for k, v in kwargs.items():
            if not v:
                continue
            if k not in sch_fields:
                self.logger.warning(f'Ignoring invalid field {k} in filter')
                continue

            ftype = schema.field(k).type
            if k in merge_fields:
                k = merge_fields[k]

            if isinstance(v, list):
                infld = []
                notinfld = []
                or_filters = None
                for e in v:
                    if isinstance(e, str) and e.startswith("!"):
                        if ftype == 'int64':
                            notinfld.append(int(e[1:]))
                        else:
                            notinfld.append(e[1:])
                    else:
                        if ftype == 'int64':
                            if or_filters is not None:
                                or_filters = or_filters | \
                                    self._cons_int_filter(k, e)
                            else:
                                or_filters = self._cons_int_filter(k, e)
                        else:
                            infld.append(e)
                if infld and notinfld:
                    filters = filters & (ds.field(k).isin(infld) &
                                         ~ds.field(k).isin(notinfld))
                elif infld:
                    filters = filters & (ds.field(k).isin(infld))
                elif notinfld:
                    filters = filters & (~ds.field(k).isin(notinfld))

                if or_filters is not None:
                    filters = filters & (or_filters)
            else:
                if isinstance(v, str) and v.startswith("!"):
                    if ftype == 'int64':
                        filters = filters & (ds.field(k) != int(v[1:]))
                    else:
                        filters = filters & (ds.field(k) != v[1:])
                else:
                    if ftype == 'int64':
                        filters = filters & self._cons_int_filter(k, v)
                    else:
                        filters = filters & (ds.field(k) == v)

        return filters

    def _get_table_directory(self, table_name: str, coalesced: bool) -> str:
        """Return the directory name for the table specified

        :param table_name: str, The table for which you want the folder
        :param coalesced: bool, True if you want the folder for the coalesced
                          data
        :returns: folder for the specified table name
        :rtype: str

        """
        if coalesced:
            folder = self.cfg.get('coalescer', {})\
                .get('coalesce-directory',
                     f'{self.cfg.get("data-directory")}/coalesced')
        else:
            folder = f'{self.cfg.get("data-directory")}'

        if table_name:
            return f'{folder}/{table_name}'
        else:
            return folder

    def _get_default_vals(self) -> dict:
        return({
            pa.string(): "",
            pa.int32(): 0,
            pa.int64(): 0,
            pa.float32(): 0.0,
            pa.float64(): 0.0,
            pa.date64(): 0.0,
            pa.bool_(): False,
            pa.list_(pa.string()): [],
            pa.list_(pa.int64()): [],
        })
