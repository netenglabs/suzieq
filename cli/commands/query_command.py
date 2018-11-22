#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
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
def sql(query: str, view: str = 'latest', start_time: str = '',
        end_time: str = ''):
    """
    Generic SQL query on the data
    """
    ctxt = context.get_context()
    query = query.strip()

    # The following madness is because nubia seems to swallow the last quote
    words = query.split()
    if "'" in words[-1] and not re.search(r"'(?=')", words[-1]):
        words[-1] += "'"
        query = ' '.join(words)

    df = get_query_output(query, ctxt.cfg, ctxt.schemas, start_time, end_time,
                          view)
    print(df)


@command("describe-table")
@argument("table", type=str, positional=True)
async def describe_table(table):
    "Describes the fields for a given table"

    ctxt = context.get_context()
    if table not in ctxt.schemas:
        print('ERROR: Unknown table {}'.format(table))
        return

    entries = [{'name': x['name'], 'type': x['type']}
               for x in ctxt.schemas[table]]
    df = pd.DataFrame.from_dict(entries)

    cprint(df)
