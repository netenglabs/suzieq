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
    '''This is the show command class.
    For each command, ensure the argument names match the field name in the
    schema to enable build_sql_str to do its magic'''

    @argument("hostname", description="Name of host to qualify selection")
    @argument("start_time",
              description="Start of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("end_time",
              description="End of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("view", description="view all records or just the latest",
              choices=['all', 'latest'])
    def __init__(self, hostname: str = '', start_time: str = '',
                 end_time: str = '', view: str = 'latest') -> None:
        self._cfg = suzieq.utils.load_sq_config(validate=False)
        self._schemas = suzieq.utils.get_schemas(self._cfg['schema-directory'])
        self.hostname = hostname
        self.start_time = start_time
        self.end_time = end_time
        self.view = view

    @property
    def cfg(self):
        return self._cfg

    @property
    def schemas(self):
        return self._schemas
    """show various pieces of information"""

    @command('bgp')
    @argument("peer", description="Name of peer to qualify show")
    @argument("vrf", description="VRF to qualify show")
    def show_bgp(self, peer: str = None, vrf: str = None):
        """
        Show BGP
        """
        order_by = 'order by hostname, vrf, peer'
        df = self.get_table_df('bgp', self.start_time, self.end_time,
                               self.view, order_by,
                               hostname=self.hostname, vrf=vrf, peer=peer)
        print(df)

    @command('interfaces')
    @argument("ifname", description="interface name to qualify show")
    def show_interfaces(self, ifname: str = None):
        """
        Show interfaces
        """
        # Get the default display field names
        order_by = 'order by hostname, ifname'
        df = self.get_table_df('interfaces', self.start_time, self.end_time,
                               self.view, order_by,
                               hostname=self.hostname, ifname=ifname)
        print(df)

    @command('lldp')
    @argument("ifname", description="interface name to qualify show")
    def show_lldp(self, ifname: str = None):
        """
        Show LLDP info
        """
        # Get the default display field names
        order_by = 'order by hostname, ifname'
        df = self.get_table_df('lldp', self.start_time, self.end_time,
                               self.view, order_by,
                               hostname=self.hostname, ifname=ifname)
        print(df)

    @command('filesystem')
    @argument("mountPoint", description="Mountpoint to filter by")
    @argument("usedPercent", description="show only if used percentage is >=")
    def show_fs(self, mountPoint: str = None, usedPercent: str = None):
        """
        Show filesystem info
        """
        # Get the default display field names
        order_by = 'order by hostname, mountPoint'
        df = self.get_table_df('fs', self.start_time, self.end_time,
                               self.view, order_by,
                               hostname=self.hostname, mountPoint=mountPoint,
                               usedPercent=usedPercent)
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

    def get_table_df(self, table: str, start_time: str, end_time: str,
                     view: str, order_by: str, **kwargs):
        '''Build query string and get dataframe'''

        qstr = self.build_sql_str(table, start_time, end_time, view,
                                  order_by, **kwargs)
        cprint(qstr)
        df = get_output(qstr, self.cfg, self.schemas,
                        start_time, end_time, view)
        return df

    def build_sql_str(self, table: str, start_time: str,
                      end_time: str, view: str, order_by: str, **kwargs):
        '''Workhorse routine to build the actual SQL query string'''

        sch = self.schemas.get(table)
        if not sch:
            print('Unknown table {}, no schema found for it', table)
            return ''

        fields = []
        wherestr = ''
        for field in sch:
            loc = field.get('display', None)
            if loc is not None:
                fields.insert(loc, field['name'])

        if 'timestamp' not in fields:
            fields.append('from_unixtime(timestamp/1000) as timestamp')

        first = True
        for kwd in kwargs:
            if not kwargs[kwd]:
                continue

            if first:
                prefix = 'where'
                first = False
            else:
                prefix = 'and'
            wherestr += " {} {}=='{}'".format(prefix, kwd, kwargs[kwd])

        if view != 'latest':
            timestr = (" and timestamp(timestamp/1000) > timestamp('{}') and "
                       "timestamp(timestamp/1000) < timestamp('{}') "
                       .format(start_time, end_time))
            wherestr += timestr
            order_by = 'order by timestamp'

        output = 'select {} from {} {} {}'.format(', '.join(fields), table,
                                                  wherestr, order_by)
        return output

def get_output(query_string: str, cfg, schemas,
               start_time='', end_time='', view='latest'):

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
        #if 'timestamp' in df.columns:
        #    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    return df
