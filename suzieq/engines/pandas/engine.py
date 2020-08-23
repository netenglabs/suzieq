import os
import sys
from concurrent.futures import ProcessPoolExecutor as Executor
from pathlib import Path
from importlib import import_module
from copy import deepcopy


try:
    # We need this if we're switching the engine from Pandas to Modin
    import ray
except ImportError:
    pass
import pandas as pd
import pyarrow.parquet as pa

from suzieq.engines.base_engine import SqEngine
from suzieq.utils import get_latest_files, SchemaForTable, build_query_str


class SqPandasEngine(SqEngine):
    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs) -> pd.DataFrame:
        """Use Pandas instead of Spark to retrieve the data"""

        MAX_FILECNT_TO_READ_FOLDER = 10000

        self.cfg = cfg

        table = kwargs.pop("table")
        start = kwargs.pop("start_time")
        end = kwargs.pop("end_time")
        view = kwargs.pop("view")
        sort_fields = kwargs.pop("sort_fields")
        ign_key_fields = kwargs.pop("ign_key", [])
        addnl_fields = kwargs.pop("addnl_fields", [])

        for f in ['active', 'timestamp']:
            if f not in addnl_fields:
                addnl_fields.append(f)

        sch = SchemaForTable(table, schema=schemas)
        phy_table = sch.get_phy_table_for_table()

        folder = self._get_table_directory(phy_table)

        # Restrict to a single DC if thats whats asked
        if "namespace" in kwargs:
            v = kwargs["namespace"]
            if v:
                if not isinstance(v, list):
                    folder += "/namespace={}/".format(v)

        fcnt = self.get_filecnt(folder)

        if fcnt == 0:
            return pd.DataFrame()

        # We are going to hard code use_get_files until we have some autoamted testing
        use_get_files = False

        # use_get_files = (
        #    (fcnt > MAX_FILECNT_TO_READ_FOLDER and view == "latest") or
        #    start or end
        # )

        if use_get_files:
            # Switch to more efficient method when there are lotsa files
            # Reduce I/O since that is the worst drag
            key_fields = []
            if len(kwargs.get("namespace", [])) > 1:
                del kwargs["namespace"]
            files = get_latest_files(folder, start, end, view)
        else:
            # ign_key_fields contains key fields that are not partition cols
            key_fields = [i for i in sch.key_fields()
                          if i not in ign_key_fields]
            filters = self.build_pa_filters(start, end, key_fields, **kwargs)

        if "columns" in kwargs:
            columns = kwargs["columns"]
            del kwargs["columns"]
        else:
            columns = ["default"]

        fields = sch.get_display_fields(columns)
        for f in addnl_fields:
            if f not in fields:
                fields.append(f)

        # Create the filter to select only specified columns
        addnl_filter = kwargs.pop('add_filter', None)
        query_str = build_query_str(key_fields, sch, **kwargs)

        # Add the ignored fields back to key fields to ensure we
        # do the drop_duplicates correctly below incl reading reqd cols
        key_fields.extend(ign_key_fields)

        # Handle the case where key fields are missing from display fields
        fldset = set(fields)
        kfldset = set(key_fields)
        add_flds = kfldset.difference(fldset)
        if add_flds:
            fields.extend(list(add_flds))

        if addnl_filter:
            # This is for special cases that are specific to an object
            if not query_str:
                query_str = addnl_filter
            else:
                query_str += ' and {}'.format(addnl_filter)

        # Restore the folder to what it needs to be
        folder = self._get_table_directory(phy_table)
        if use_get_files:
            if not query_str:
                query_str = "active == True"

            pdf_list = []
            with Executor(max_workers=8) as exe:
                jobs = [
                    exe.submit(self.read_pq_file, f, fields, query_str)
                    for f in files
                ]
                pdf_list = [job.result() for job in jobs]

            if pdf_list:
                final_df = pd.concat(pdf_list)
            else:
                final_df = pd.DataFrame(columns=fields)

        elif view == "latest":
            if not query_str:
                # Make up a dummy query string to avoid if/then/else
                query_str = "timestamp != 0"

            try:
                final_df = (
                    pa.ParquetDataset(
                        folder, filters=filters or None, validate_schema=False
                    )
                    .read(columns=fields)
                    .to_pandas(split_blocks=True, self_destruct=True)
                    .query(query_str)
                    .drop_duplicates(subset=key_fields, keep="last")
                    .query("active == True")
                )
            except pa.lib.ArrowInvalid:
                return pd.DataFrame(columns=fields)
        else:
            if not query_str:
                # Make up a dummy query string to avoid if/then/else
                query_str = 'timestamp != "0"'

            try:
                final_df = (
                    pa.ParquetDataset(
                        folder, filters=filters or None, validate_schema=False
                    )
                    .read(columns=fields)
                    .to_pandas()
                    .query(query_str)
                )
            except pa.lib.ArrowInvalid:
                return pd.DataFrame(columns=fields)

        if 'active' not in columns:
            final_df.drop(columns=['active'], axis=1, inplace=True)
            fields.remove('active')

        final_df = df_timestamp_to_datetime(final_df)
        fields = [x for x in fields if x in final_df.columns]
        if sort_fields and all(x in sort_fields for x in fields):
            return final_df[fields].sort_values(by=sort_fields)
        else:
            return final_df[fields]

    def get_object(self, objname: str, iobj):
        module = import_module("suzieq.engines.pandas." + objname)
        eobj = getattr(module, "{}Obj".format(objname.title()))
        return eobj(iobj)

    def get_filecnt(self, path="."):
        total = 0
        if os.path.isdir(path):
            for entry in os.scandir(path):
                if entry.is_file():
                    total += 1
                elif entry.is_dir():
                    total += self.get_filecnt(entry.path)
        return total

    def build_pa_filters(self, start_tm: str, end_tm: str, key_fields: list,
                         **kwargs):
        """Build filters for predicate pushdown of parquet read"""

        # The time filters first
        timeset = []
        if start_tm and not end_tm:
            timeset = pd.date_range(
                start=pd.to_datetime(start_tm, infer_datetime_format=True),
                periods=2,
                freq="15min",
            )
            filters = [[("timestamp", ">=", timeset[0].timestamp() * 1000)]]
        elif end_tm and not start_tm:
            timeset = pd.date_range(
                end=pd.to_datetime(
                    end_tm, infer_datetime_format=True),
                periods=2,
                freq="15min",
            )
            filters = [
                [("timestamp", "<=", timeset[-1].timestamp() * 1000)]]
        elif start_tm and end_tm:
            timeset = [
                pd.to_datetime(start_tm, infer_datetime_format=True),
                pd.to_datetime(end_tm, infer_datetime_format=True),
            ]
            filters = [
                [
                    ("timestamp", ">=", timeset[0].timestamp() * 1000),
                    ("timestamp", "<=", timeset[-1].timestamp() * 1000),
                ]
            ]
        else:
            filters = []

        # pyarrow's filters are in Disjunctive Normative Form and so filters
        # can get a bit long when lists are present in the kwargs

        for k, v in kwargs.items():
            if v and k in key_fields:
                if isinstance(v, list):
                    kwdor = []
                    for e in v:
                        if e.startswith("!"):
                            e = e[1:]
                            op = "!="
                        else:
                            op = "=="

                        if not filters:
                            kwdor.append(
                                [tuple(("{}".format(k), op, "{}".format(e)))]
                            )
                        else:
                            for entry in filters:
                                foo = deepcopy(entry)
                                foo.append(
                                    tuple(("{}".format(k), op, "{}".format(
                                        e)))
                                )
                                kwdor.append(foo)

                    filters = kwdor
                else:
                    if v.startswith("!"):
                        v = v[1:]
                        op = "!="
                    else:
                        op = "=="

                    if not filters:
                        filters.append([tuple(("{}".format(k), op, "{}".
                                               format(v)))])
                    else:
                        for entry in filters:
                            entry.append(tuple(("{}".format(k), op, "{}".
                                                format(v))))

        return filters

    def read_pq_file(self, file: str, fields: list,
                     query_str: str) -> pd.DataFrame:
        # Sadly predicate pushdown doesn't work in this method.
        # We use query on the output to filter
        df = pa.ParquetDataset(file).read(columns=fields).to_pandas()
        pth = Path(file).parts
        for elem in pth:
            if "=" in elem:
                k, v = elem.split("=")
                df[k] = v
        return df.query(query_str)

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

        tables = []
        if dfolder:
            p = Path(dfolder)
            tables = [dir.parts[-1] for dir in p.iterdir()
                      if dir.is_dir() and not dir.parts[-1].startswith('_')]
            namespaces = kwargs.get('namespace', [])
            for dc in namespaces:
                tables = list(filter(
                    lambda x: os.path.exists('{}/{}/namespace={}'.format(
                        dfolder, x, dc)), tables))

        return tables


def df_timestamp_to_datetime(df):
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df.timestamp.astype(str), unit="ms")
    return df
