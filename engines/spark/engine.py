#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import re
from datetime import datetime
import json
from collections import OrderedDict
from importlib import import_module

import pandas as pd

from suzieq.engines.base_engine import SQEngine
from suzieq.utils import get_display_fields
from suzieq.livylib import get_livysession, exec_livycode

code_tmpl = """
import sys
import datetime
from suzieq.utils import get_latest_files

files = dict()
for k in {1}:
    v = get_latest_files("{0}" + "/" + k, start="{3}", end="{4}")
    files[k] = v

for k, v in files.items():
    spark.read.option("basePath", "{0}").load(v).createOrReplaceTempView(k)

x={2}
for k in {1}:
  spark.catalog.dropTempView(k)
x
"""

code_viewall_tmpl = """
import sys

for k in {1}:
    spark.read.option("basePath", "{0}").load("{0}/" + k).createOrReplaceTempView(k)

x={2}
for k in {1}:
  spark.catalog.dropTempView(k)
x

"""


class SQSparkEngine(SQEngine):
    def __init__(self):
        # TBD: Check if livy session exists, if not start it
        pass

    def get_object(self, objname: str, iobj):
        module = import_module("suzieq.engines.spark." + objname)
        eobj = getattr(module, "{}Obj".format(objname))
        return eobj(iobj)

    def get_table_df(self, cfg, schemas, **kwargs):

        table = kwargs["table"]
        start_time = kwargs["start_time"]
        end_time = kwargs["end_time"]
        view = kwargs["view"]
        sort_fields = kwargs["sort_fields"]

        for field in ["table", "start_time", "end_time", "view", "sort_fields"]:
            del kwargs[field]

        sch = schemas.get(table)
        if not sch:
            print("Unknown table {}, no schema found for it".format(table))
            return ""
        qstr = self.build_sql_str(
            table, start_time, end_time, view, sort_fields, sch, **kwargs
        )
        if not qstr:
            return None

        df = self.get_query_df(qstr, cfg, schemas, start_time, end_time, view)
        # df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp'],
        #                                                downcast='float'),
        #                                  unit='ms')
        return df

    def build_sql_str(
        self,
        table: str,
        start_time: str,
        end_time: str,
        view: str,
        sort_fields: list,
        sch,
        **kwargs
    ):
        """Workhorse routine to build the actual SQL query string"""

        fields = []
        wherestr = "where active==True "
        order_by = ""
        if "columns" in kwargs:
            columns = kwargs["columns"]
            del kwargs["columns"]
        else:
            columns = "default"

        fields = get_display_fields(table, columns, sch)

        if "timestamp" not in fields:
            # fields.append('from_unixtime(timestamp/1000) as timestamp')
            fields.append("timestamp")

        for i, kwd in enumerate(kwargs):
            if not kwargs[kwd]:
                continue

            prefix = "and"
            value = kwargs[kwd]

            if isinstance(value, list):
                kwdstr = ""
                for j, e in enumerate(value):
                    prefix1 = " or" if j else "("
                    kwdstr += "{} {} == '{}'".format(prefix1, kwd, e)
                kwdstr += ")"
            else:
                kwdstr = " {}=='{}'".format(kwd, value)

            wherestr += " {} {}".format(prefix, kwdstr)

        if view != "latest":
            timestr = ""
            if start_time:
                timestr = " and timestamp(timestamp/1000) > timestamp('{}')".format(
                    start_time
                )
            if end_time:
                timestr += " and timestamp(timestamp/1000) < timestamp('{}') ".format(
                    end_time
                )
            if timestr:
                wherestr += timestr
            order_by = "order by timestamp"
        else:
            if sort_fields:
                order_by = "order by {}".format(", ".join(sort_fields))

        output = "select {} from {} {} {}".format(
            ", ".join(fields), table, wherestr, order_by
        )
        return output

    def get_spark_code(
        self,
        qstr: str,
        cfg,
        schemas,
        start: str = "",
        end: str = "",
        view: str = "latest",
    ) -> str:
        """Get the Table creation and destruction code for query string"""

        # SQL syntax has keywords separated by space, multiple values for a
        # keyword separated by comma.
        qparts = re.split(r"(?<!,)\s+", qstr)
        tables = []
        counter = []

        if counter or view == "all":
            # We need to apply time window to sql
            windex = [i for i, x in enumerate(qparts) if x.lower() == "where"]
            timestr = "("
            if start:
                ssecs = (
                    int(datetime.strptime(start, "%Y-%m-%d %H:%M:%S").strftime("%s"))
                    * 1000
                )
                timestr += "timestamp > {} ".format(ssecs)
            if end:
                esecs = (
                    int(datetime.strptime(end, "%Y-%m-%d %H:%M:%S").strftime("%s"))
                    * 1000
                )
                if timestr != "(":
                    timestr += " and timestamp < {})".format(esecs)
                else:
                    timestr += "(timestamp < {})".format(esecs)
            if timestr != "(":
                if windex:
                    timestr += " and "
                    qparts.insert(windex[0] + 1, timestr)
                else:
                    timestr = " where {}".format(timestr)

        qstr = " ".join(qparts)

        indices = [i for i, x in enumerate(qparts) if x.lower() == "from"]
        indices += [i for i, x in enumerate(qparts) if x.lower() == "join"]

        print(qstr)
        for index in indices:
            words = re.split(r",\s*", qparts[index + 1])
            for table in words:
                if table in schemas and table not in tables:
                    tables.append(table)

        sstr = 'spark.sql("{0}").toJSON().collect()'.format(qstr)
        if view == "latest":
            code = code_tmpl.format(cfg["data-directory"], tables, sstr, start, end)
        else:
            code = code_viewall_tmpl.format(cfg["data-directory"], tables, sstr)
        return code

    def get_query_df(
        self,
        query_string: str,
        cfg,
        schemas,
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
    ) -> pd.DataFrame:

        df = None

        try:
            session_url = get_livysession()
        except Exception:
            session_url = None

        if not session_url:
            print("Unable to find valid, active Livy session")
            print("Queries will not execute")
            return df

        query_string = query_string.strip()

        # The following madness is because nubia swallows the last quote
        words = query_string.split()
        if "'" in words[-1] and not re.search(r"'(?=')?", words[-1]):
            words[-1] += "'"
            query_string = " ".join(words)

        code = self.get_spark_code(
            query_string, cfg, schemas, start_time, end_time, view
        )
        output = exec_livycode(code, session_url)
        if output["status"] != "ok":
            df = {
                "error": output["status"],
                "type": output["ename"],
                "errorMsg": output["evalue"].replace("\\n", " ").replace('u"', ""),
            }
        else:
            # We don't use read_json because that call doesn't preserve column
            # order.
            jout = json.loads(
                output["data"]["text/plain"]
                .replace("', u'", ", ")
                .replace("u'", "")
                .replace("'", ""),
                object_pairs_hook=OrderedDict,
            )
            df = pd.DataFrame.from_dict(jout)

        if df is not None and "error" not in df and "__index_level_0__" in df.columns:
            df = df.drop(columns=["__index_level_0__"])

        return df
