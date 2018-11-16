#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import asyncio
import sys
import os
import re
import socket
from pathlib import Path
import json
from datetime import datetime
from collections import OrderedDict


import pandas as pd
import typing
from termcolor import cprint
from nubia import command, argument, context

sys.path.append('/home/ddutt/work/')
import suzieq.livylib
import suzieq.utils
from commands.utils import get_spark_code

code_tmpl = '''
import sys
sys.path.append("/home/ddutt/work/suzieq/")
from livylib import get_latest_files

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
'''

counter_code_tmpl = '''
import pyspark.sql.functions as F
from pyspark.sql.window import Window

for k in {1}:
    spark.read.option("basePath", "{0}").load("{0}/" + k).createOrReplaceTempView(k)

cntrdf={2}

col_name = "{3}"
cntrdf = cntrdf \
             .withColumn('prevTime',
                         F.lag(cntrdf.timestamp).over(Window.partitionBy()
                                                      .orderBy('timestamp')))
cntrdf = cntrdf \
             .withColumn('prevBytes',
                         F.lag(col_name).over(Window.partitionBy()
                                              .orderBy('timestamp')))

cntrdf = cntrdf \
             .withColumn("rate",
                         F.when(F.isnull(F.col(col_name) - cntrdf.prevBytes), 0)
                         .otherwise((F.col(col_name) - cntrdf.prevBytes)*8 /
                                    (cntrdf.timestamp.astype('double')-cntrdf.prevTime.astype('double')))) \
             .drop('prevTime', 'prevBytes')

for k in {1}:
  spark.catalog.dropTempView(k)

cntrdf.toJSON().collect()
'''


@command
@argument("query", description="SQL statement", aliases=["i"])
@argument("start_time",
          description="Start of time window in YYYY-MM-dd HH:mm:SS format")
@argument("end_time",
          description="End of time window in YYYY-MM-dd HH:mm:SS format")
def sql(query: str, start_time: str = '', end_time: str = ''):
    """
    This will lookup the hostnames and print the corresponding IP addresses
    """
    ctx = context.get_context()
    if not ctx.cfg:
        cfg = suzieq.utils.load_sq_config()
        ctx.cfg = cfg
    else:
        cfg = cfg.ctx

    schemas = suzieq.utils.get_schemas(cfg['schema-directory'])

    try:
        session_url = suzieq.livylib.get_livysession()
    except Exception:
        session_url = None

    if not session_url:
        print('Unable to find valid, active Livy session')
        print('Queries will not execute')
        return

    query = query.strip()

    # The following madness is because nubia seems to swallow the last quote
    words = query.split()
    if "'" in words[-1] and not re.search(r"'(?=')", words[-1]):
        words[-1] += "'"
        query = ' '.join(words)

    code = get_spark_code(query, cfg, schemas, start_time, end_time)
    output = suzieq.livylib.exec_livycode(code, session_url)
    if output['status'] != 'ok':
        df = {'error': output['status'],
              'type': output['ename'],
              'errorMsg': output['evalue'].replace('\\n', ' ')
                                          .replace('u\"', '')}
    else:
        # We don't use read_json because that call doesn't preserve column
        # order.
        jout = json.loads(output['data']['text/plain']
                          .replace("\', u\'", ', ')
                          .replace("u\'", '')
                          .replace("\'", ''), object_pairs_hook=OrderedDict)
        df = pd.DataFrame.from_dict(jout)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    print(df)


@command("describe-table")
@argument("table", type=str)
async def describe_table(table):
    "Calculates the triple of the input value"

    ctx = context.get_context()
    if not ctx.cfg:
        cfg = suzieq.utils.load_sq_config()
        ctx.cfg = cfg
    else:
        cfg = cfg.ctx

    dfolder = cfg['data-directory']
    schemas = suzieq.utils.get_schemas(cfg['schema-directory'])

    if table not in schemas:
        print('ERROR: Unknown table {}'.format(table))
        return

    entries = [{'name': x['name'], 'type': x['type']}
               for x in schemas[table]]
    df = pd.DataFrame.from_dict(entries)

    cprint(df)



