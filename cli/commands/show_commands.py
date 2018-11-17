#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#


import re
import sys
from pathlib import Path
import json
from collections import OrderedDict


import pandas as pd
from termcolor import cprint
from nubia import command, argument
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
    """show various pieces of information"""

    @command('bgp')
    @argument("hostname", description="Name of host to qualify show")
    @argument("peer", description="Name of peer to qualify show")
    @argument("vrf", description="VRF to qualify show")
    @argument("start_time",
              description="Start of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("end_time",
              description="End of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("view", description="view all records or just the latest",
              choices=['all', 'latest'])
    def show_bgp(self, hostname: str = None, peer: str = None, vrf: str = None,
                 start_time: str = '', end_time: str = '', view: str = 'latest'):
        """
        Show BGP
        """

        # Get the default display field names
        sch = self.schemas['bgp']
        fields = []
        wherestr = ''
        for field in sch:
            loc = field.get('display', None)
            if loc is not None:
                fields.insert(loc, field['name'])

        if 'timestamp' not in fields:
            fields.append('timestamp')

        if hostname:
            wherestr += "where hostname=='{}'".format(hostname)

        if peer:
            wherestr += " and peer=='{}'".format(peer)

        if vrf:
            wherestr += " and vrf=='{}'".format(vrf)

        if view == 'latest':
            order_by_str = 'order by hostname, vrf, peer'
        else:
            timestr = (" and timestamp(timestamp/1000) > timestamp('{}') and "
                       "timestamp(timestamp/1000) < timestamp('{}') "
                       .format(start_time, end_time))
            wherestr += timestr
            order_by_str = 'order by timestamp'

        bgp_sqlstr = 'select {} from bgp {} {}'\
                     .format(', '.join(fields), wherestr, order_by_str)

        cprint(bgp_sqlstr)
        df = get_output(bgp_sqlstr, self.cfg, self.schemas,
                        start_time, end_time, view)
        print(df)

    @command('interfaces')
    @argument("hostname", description="Name of host to qualify show")
    @argument("ifname", description="interface name to qualify show")
    @argument("start_time",
              description="Start of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("end_time",
              description="End of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("view", description="view all records or just the latest",
              choices=['all', 'latest'])
    def show_interfaces(self, hostname: str = None, ifname: str = None,
                        start_time: str = '', end_time: str = '',
                        view: str = 'latest'):
        """
        Show interfaces
        """
        # Get the default display field names
        sch = self.schemas['interfaces']
        fields = []
        wherestr = ''
        for field in sch:
            loc = field.get('display', None)
            if loc is not None:
                fields.insert(loc, field['name'])

        if hostname:
            wherestr += "where hostname=='{}'".format(hostname)

        if ifname:
            wherestr += " and ifname=='{}'".format(ifname)

        if_sqlstr = 'select {} from interfaces {} order by hostname, ifname'\
                     .format(', '.join(fields), wherestr)

        cprint(if_sqlstr)
        df = get_output(if_sqlstr, self.cfg, self.schemas,
                        start_time, end_time, view)
        print(df)

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


def get_output(query_string: str, cfg, schemas,
               start_time='', end_time='', view: str = 'latest'):

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

    code = get_spark_code(query_string, cfg, schemas, start_time, end_time,
                          view)
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
