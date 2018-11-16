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
from commands.utils import get_spark_code

sys.path.append('/home/ddutt/work/')
import suzieq.livylib
import suzieq.utils


@command('show')
class ShowCommand:
    "This is the wrapper show command"

    def __init__(self) -> None:
        self._cfg = suzieq.utils.load_sq_config(validate=False)
        self._schemas = suzieq.utils.get_schemas(self._cfg['schema-directory'])

    @property
    def cfg(self):
        return self._cfg

    @property
    def schemas(self):
        return self._schemas
    """This is the super command help"""

    @command('bgp')
    @argument("hostname", description="Name of host to qualify show")
    @argument("peer", description="Name of peer to qualify show")
    @argument("vrf", description="VRF to qualify show")        
    @argument("start_time",
              description="Start of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("end_time",
              description="End of time window in YYYY-MM-dd HH:mm:SS format")
    def show_bgp(self, hostname: str = None, peer: str = None, vrf: str = None,
                 start_time: str=None, end_time: str=None):
        """
        Show BGP
        """

        ctx = context.get_context()
        # Get the default display field names
        sch = self.schemas['bgp']
        fields = []
        wherestr = ''
        for field in sch:
            loc = field.get('display', None)
            if loc is not None:
                fields.insert(loc, field['name'])

        if hostname:
            wherestr += "where hostname=='{}'".format(hostname)

        if peer:
            wherestr += " and where peer=='{}'".format(peer)

        if vrf:
            wherestr += " and where vrf=='{}'".format(vrf)

        bgp_sqlstr = 'select {} from bgp {} order by hostname, vrf, peer'\
                     .format(', '.join(fields), wherestr)

        cprint(bgp_sqlstr)
        df = get_output(bgp_sqlstr, ctx, self.cfg, self.schemas)
        print(df)

    @command('interfaces')
    def show_interfaces(self):
        """
        Show interfaces
        """
        cprint("stuff={}".format('interfaces'))

    @command("tables")
    def show_tables(self):
        """
        List all the tables we know of given the Suzieq config
        """

        dfolder = self.cfg['data-directory']

        if dfolder:
            p = Path(dfolder)
            tables = [{'table': dir.parts[-1]} for dir in p.iterdir()
                      if dir.is_dir() and not dir.parts[-1].startswith('_')]
            df = pd.DataFrame.from_dict(tables)
            cprint(df)


def get_output(query_string: str, ctx, cfg, schemas,
               start_time='', end_time=''):

    try:
        session_url = suzieq.livylib.get_livysession()
    except Exception:
        session_url = None

    if not session_url:
        print('Unable to find valid, active Livy session')
        print('Queries will not execute')
        return

    query_string = query_string.strip()

    # The following madness is because nubia seems to swallow the last quote
    words = query_string.split()
    if "'" in words[-1] and not re.search(r"'(?=')", words[-1]):
        words[-1] += "'"
        query_string = ' '.join(words)

    code = get_spark_code(query_string, cfg, schemas, start_time, end_time)
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

    return df
