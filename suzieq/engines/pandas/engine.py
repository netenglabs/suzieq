import os
import logging
from pathlib import Path
from importlib import import_module
import pyarrow.dataset as ds
from itertools import zip_longest

import pandas as pd
import pyarrow.parquet as pa
import numpy as np

from suzieq.engines.base_engine import SqEngine


class SqPandasEngine(SqEngine):
    def __init__(self):
        self.logger = logging.getLogger()

    def get_table_df(self, cfg, **kwargs) -> pd.DataFrame:
        """Use Pandas instead of Spark to retrieve the data"""

        self.cfg = cfg

        table = kwargs.pop("table")
        start = kwargs.pop("start_time")
        end = kwargs.pop("end_time")
        view = kwargs.pop("view")
        fields = kwargs.pop("columns")
        addnl_filter = kwargs.pop("add_filter", None)
        key_fields = kwargs.pop("key_fields")
        merge_fields = kwargs.pop('merge_fields', {})

        folder = self._get_table_directory(table)

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
        try:
            dirs = Path(folder)
            datasets = []
            for elem in dirs.iterdir():
                # Additional processing around sqvers filtering and data
                if 'sqvers=' not in str(elem):
                    continue
                if sqvers and f'sqvers={sqvers}' != elem:
                    continue
                elif need_sqvers:
                    vers = float(str(elem).split('=')[-1])
                    if vers > max_vers:
                        max_vers = vers

                datasets.append(ds.dataset(elem, format='parquet',
                                           partitioning='hive'))

            if not datasets:
                datasets = [ds.dataset(folder, format='parquet',
                                       partitioning='hive')]

            # Build the filters for predicate pushdown
            master_schema = self._build_master_schema(datasets)

            filters = self.build_ds_filters(
                start, end, master_schema, merge_fields=merge_fields, **kwargs)

            final_df = ds.dataset(datasets) \
                         .to_table(filter=filters, columns=fields) \
                         .to_pandas(self_destruct=True) \
                         .query(query_str)

            if merge_fields:
                # These are key fields that need to be set right before we do
                # the drop duplicates to avoid missing out all the data
                for field in merge_fields:
                    newfld = merge_fields[field]
                    if (field in final_df.columns and
                            newfld in final_df.columns):
                        final_df[newfld] = np.where(final_df[newfld],
                                                    final_df[newfld],
                                                    final_df[field])

            if (not final_df.empty and (view == 'latest') and
                    all(x in final_df.columns for x in key_fields)):
                final_df = final_df.set_index(key_fields) \
                                   .sort_values(by='timestamp') \
                                   .query('~index.duplicated(keep="last")') \
                                   .reset_index()
        except (pa.lib.ArrowInvalid, OSError):
            return pd.DataFrame(columns=fields)

        fields = [x for x in final_df.columns if x in fields]
        if need_sqvers:
            final_df['sqvers'] = max_vers
            fields.insert(0, 'sqvers')

        return final_df[fields]

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
            elif sch_set.issuperset(msch):
                msch = sch
            else:
                for fld in sch_set-msch_set:
                    index = sch.get_field_index(fld.name)
                    msch.insert(index, fld)

        return msch

    def get_object(self, objname: str, iobj):
        module = import_module("suzieq.engines.pandas." + objname)
        eobj = getattr(module, "{}Obj".format(objname.title()))
        return eobj(iobj)

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

    def build_ds_filters(self, start_tm: str, end_tm: str,
                         schema: pa.lib.Schema,
                         **kwargs) -> ds.Expression:
        """The new style of filters using dataset instead of ParquetDataset"""

        merge_fields = kwargs.pop('merge_fields', {})
        # The time filters first
        timeset = []
        if start_tm and not end_tm:
            timeset = pd.date_range(
                start=pd.to_datetime(start_tm, infer_datetime_format=True),
                periods=2,
                freq="15min",
            )
            filters = ds.field("timestamp") >= (timeset[0].timestamp() * 1000)
        elif end_tm and not start_tm:
            timeset = pd.date_range(
                end=pd.to_datetime(
                    end_tm, infer_datetime_format=True),
                periods=2,
                freq="15min",
            )
            filters = ds.field("timestamp") <= (timeset[-1].timestamp() * 1000)
        elif start_tm and end_tm:
            timeset = [
                pd.to_datetime(start_tm, infer_datetime_format=True),
                pd.to_datetime(end_tm, infer_datetime_format=True),
            ]
            filters = ((ds.field("timestamp") >= (timeset[0].timestamp() * 1000))
                       & (ds.field("timestamp") <= (timeset[-1].timestamp() * 1000)))
        else:
            filters = (ds.field("timestamp") != 0)

        sch_fields = schema.names
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
                            if or_filters:
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

                if or_filters:
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

    def _get_table_directory(self, table):
        assert table
        folder = "{}/{}".format(self.cfg.get("data-directory"), table)
        # print(f"FOLDER: {folder}", file=sys.stderr)
        return folder

    def get_tables(self, cfg, **kwargs):
        """finds the tables that are available"""
        if not getattr(self, 'cfg', None):
            self.cfg = cfg
        dfolder = self.cfg['data-directory']
        tables = set()
        if dfolder:
            dfolder = os.path.abspath(dfolder) + '/'
            p = Path(dfolder)
            namespaces = kwargs.get('namespace', [])
            if not namespaces:
                ns = set([x.parts[-1].split('=')[1]
                          for x in p.glob('**/namespace=*')])
            else:
                ns = set(namespaces)
            for dc in ns:
                dirlist = p.glob(f'**/namespace={dc}')
                tlist = [str(x).split(z)[1].split('/')[0]
                         for x, z in list(zip_longest(dirlist, [dfolder],
                                                      fillvalue=dfolder))]
                if not tables:
                    tables = set(tlist)
                else:
                    tables.update(tlist)
        return list(tables)
