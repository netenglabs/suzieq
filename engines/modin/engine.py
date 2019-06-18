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

import modin.experimental.pandas as pd
import pyarrow.parquet as pa

from suzieq.engines.base_engine import SQEngine
from suzieq.utils import get_display_fields, get_latest_files


class SQModinEngine(SQEngine):
    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs) -> pd.DataFrame:
        """Use Pandas instead of Spark to retrieve the data"""

        table = kwargs["table"]
        start = kwargs["start_time"]
        end = kwargs["end_time"]
        view = kwargs["view"]
        sort_fields = kwargs["sort_fields"]

        for field in ["table", "start_time", "end_time", "view", "sort_fields"]:
            del kwargs[field]

        sch = schemas.get(table)
        if not sch:
            print("Unknown table {}, no schema found for it".format(table))
            return ""

        folder = "{}/{}".format(cfg.get("data-directory"), table)

        # # Restrict to a single DC if thats whats asked
        # if 'datacenter' in kwargs:
        #     v = kwargs['datacenter']
        #     if v:
        #         if len(v) == 1:
        #             folder += '/datacenter={}/'.format(v[0])

        key_fields = [f["name"] for f in sch if f.get("key", None) is not None]
        filters = self.build_pa_filters(start, end, key_fields, **kwargs)
        print(folder)

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
            if not v or f in ["groupby"]:
                continue
            if isinstance(v, str):
                query_str += "{} {}=='{}' ".format(prefix, f, v)
                prefix = "and"
            else:
                query_str += "{} {}=={} ".format(prefix, f, v)
                prefix = "and"

        if view == "latest":
            if not query_str:
                # Make up a dummy query string to avoid if/then/else
                query_str = "timestamp != 0"

            # Sadly we have to hardcode this here. Need to find a better way
            if table == "routes":
                key_fields.append("prefix")

            final_df = (
                pd.read_parquet(folder, columns=fields, filters=filters or None)
                .query(query_str)
                .drop_duplicates(subset=key_fields, keep="last", inplace=False)
                .query("active == True")
            )
        else:
            if not query_str:
                # Make up a dummy query string to avoid if/then/else
                query_str = 'timestamp != "0"'

            final_df = (
                pa.ParquetDataset(
                    folder, filters=filters or None, validate_schema=False
                )
                .read(columns=fields)
                .to_pandas()
                .query(query_str)
            )

        if view == "latest" and "active" not in kwargs:
            fields.remove("active")
            final_df.drop(columns=["active"], axis=1)

        if not final_df.empty:
            final_df["timestamp"] = pd.to_datetime(
                pd.to_numeric(final_df["timestamp"], downcast="float"), unit="ms"
            )
        if sort_fields:
            return final_df[fields].sort_values(by=sort_fields)
        else:
            return final_df[fields]

    def get_object(self, objname: str, iobj):
        module = import_module("suzieq.engines.pandas." + objname)
        eobj = getattr(module, "{}Obj".format(objname))
        return eobj(iobj)

    def get_filecnt(self, path="."):
        total = 0
        for entry in os.scandir(path):
            if entry.is_file():
                total += 1
            elif entry.is_dir():
                total += self.get_filecnt(entry.path)
        return total

    def build_pa_filters(self, start_tm: str, end_tm: str, key_fields: list, **kwargs):
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
                                    tuple(("{}".format(k), "==", "{}".format(e)))
                                )
                                kwdor.append(foo)

                    filters = kwdor
                else:
                    if not filters:
                        filters.append(tuple(("{}".format(k), "==", "{}".format(v))))
                    else:
                        for entry in filters:
                            entry.append(tuple(("{}".format(k), "==", "{}".format(v))))

        return filters

    def read_pq_file(self, file: str, fields: list, query_str: str) -> pd.DataFrame:
        # Sadly predicate pushdown doesn't work in this method.
        # We use query on the output to filter
        df = pa.ParquetDataset(file).read(columns=fields).to_pandas()
        pth = Path(file).parts
        for elem in pth:
            if "=" in elem:
                k, v = elem.split("=")
                df[k] = v
        return df.query(query_str)
