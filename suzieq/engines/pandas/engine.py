#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import os
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
from suzieq.utils import get_display_fields, get_latest_files


class SqPandasEngine(SqEngine):
    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs) -> pd.DataFrame:
        """Use Pandas instead of Spark to retrieve the data"""

        MAX_FILECNT_TO_READ_FOLDER = 10000

        table = kwargs["table"]
        start = kwargs["start_time"]
        end = kwargs["end_time"]
        view = kwargs["view"]
        sort_fields = kwargs["sort_fields"]

        for field in ["table", "start_time", "end_time", "view",
                      "sort_fields"]:
            del kwargs[field]

        sch = schemas.get(table)
        if not sch:
            raise ValueError(f"Unknown table {table}, no schema found for it")

        folder = "{}/{}".format(cfg.get("data-directory"), table)

        # Restrict to a single DC if thats whats asked
        if "datacenter" in kwargs:
            v = kwargs["datacenter"]
            if v:
                if not isinstance(v, list):
                    folder += "/datacenter={}/".format(v)

        fcnt = self.get_filecnt(folder)

        use_get_files = (
            (fcnt > MAX_FILECNT_TO_READ_FOLDER and view == "latest") or
            start or end
        )

        if use_get_files:
            # Switch to more efficient method when there are lotsa files
            # Reduce I/O since that is the worst drag
            key_fields = []
            if len(kwargs.get("datacenter", [])) > 1:
                del kwargs["datacenter"]
            files = get_latest_files(folder, start, end)
        else:
            key_fields = [f["name"] for f in sch
                          if f.get("key", None) is not None]
            # Repopulate the folder so that we can get datacenter in our result
            folder = "{}/{}".format(cfg.get("data-directory"), table)
            filters = self.build_pa_filters(start, end, key_fields, **kwargs)

        if "columns" in kwargs:
            columns = kwargs["columns"]
            del kwargs["columns"]
        else:
            columns = ["default"]

        fields = get_display_fields(table, columns, sch)

        if "active" not in fields:
            fields.append("active")

        if "timestamp" not in fields:
            fields.append("timestamp")

        # Create the filter to select only specified columns
        query_str = ""
        prefix = ""
        for f, v in kwargs.items():
            if not v or f in key_fields or f in ["groupby"]:
                continue
            if isinstance(v, str):
                query_str += "{} {}=='{}' ".format(prefix, f, v)
                prefix = "and"
            else:
                query_str += "{} {}=={} ".format(prefix, f, v)
                prefix = "and"

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

        elif view == "latest":
            if not query_str:
                # Make up a dummy query string to avoid if/then/else
                query_str = "timestamp != 0"

            # Sadly we have to hard code this for routes
            # to avoid splitting the parquet datafiles by prefix
            if table == "routes":
                key_fields.append("prefix")

            # Handle the case where key fields are missing from display fields
            fldset = set(fields)
            kfldset = set(key_fields)
            add_flds = kfldset.difference(fldset)
            if add_flds:
                fields.extend(list(add_flds))

            try:
                final_df = (
                    pa.ParquetDataset(
                        folder, filters=filters or None, validate_schema=False
                    )
                    .read(columns=fields)
                    .to_pandas()
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

        if not final_df.empty:
            final_df["timestamp"] = pd.to_datetime(
                pd.to_numeric(final_df["timestamp"], downcast="float"),
                unit="ms"
            )
        if view == 'latest' and 'active' not in columns:
            final_df.drop(columns=['active'], axis=1, inplace=True)
            fields.remove('active')

        if sort_fields:
            return final_df[fields].sort_values(by=sort_fields)
        else:
            return final_df[fields]

    def get_object(self, objname: str, iobj):
        module = import_module("suzieq.engines.pandas." + objname)
        eobj = getattr(module, "{}Obj".format(objname.title()))
        return eobj(iobj)

    def get_filecnt(self, path="."):
        total = 0
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
                pd.to_datetime(start_tm, infer_datetime_format=True),
                periods=2,
                freq="15min",
            )
            filters = [[("timestamp", ">=", timeset[0].timestamp() * 1000)]]
        elif end_tm and not start_tm:
            timeset = pd.date_range(
                pd.to_datetime(end_tm, infer_datetime_format=True),
                periods=2,
                freq="15min",
            )
            filters = [[("timestamp", "<=", timeset[-1].timestamp() * 1000)]]
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
                        if not filters:
                            kwdor.append(
                                [tuple(("{}".format(k), "==", "{}".format(e)))]
                            )
                        else:
                            for entry in filters:
                                foo = deepcopy(entry)
                                foo.append(
                                    tuple(("{}".format(k), "==", "{}".format(
                                        e)))
                                )
                                kwdor.append(foo)

                    filters = kwdor
                else:
                    if not filters:
                        filters.append(tuple(("{}".format(k), "==", "{}".
                                              format(v))))
                    else:
                        for entry in filters:
                            entry.append(tuple(("{}".format(k), "==", "{}".
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
