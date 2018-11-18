#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
import re
import json
from collections import OrderedDict

import pandas as pd
from termcolor import cprint
from nubia import command, argument, context

sys.path.append('/home/ddutt/work/')
import suzieq.livylib
from suzieq.utils import load_sq_config, get_schemas, get_query_output


@command
@argument("query", description="SQL statement", aliases=["i"])
@argument("start_time",
          description="Start of time window in YYYY-MM-dd HH:mm:SS format")
@argument("end_time",
          description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument("view", description="view all records or just the latest",
              choices=['all', 'latest'])
def sql(query: str, view: str = 'latest', start_time: str = '', end_time: str = ''):
    """
    This will lookup the hostnames and print the corresponding IP addresses
    """
    ctx = context.get_context()
    if not ctx.cfg:
        cfg = load_sq_config()
        ctx.cfg = cfg
    else:
        cfg = cfg.ctx

    schemas = get_schemas(cfg['schema-directory'])

    query = query.strip()

    # The following madness is because nubia seems to swallow the last quote
    words = query.split()
    if "'" in words[-1] and not re.search(r"'(?=')", words[-1]):
        words[-1] += "'"
        query = ' '.join(words)

    df = get_query_output(query, cfg, schemas, start_time, end_time)
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

    schemas = suzieq.utils.get_schemas(cfg['schema-directory'])

    if table not in schemas:
        print('ERROR: Unknown table {}'.format(table))
        return

    entries = [{'name': x['name'], 'type': x['type']}
               for x in schemas[table]]
    df = pd.DataFrame.from_dict(entries)

    cprint(df)
