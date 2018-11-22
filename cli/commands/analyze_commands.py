#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
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
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.utils import load_sq_config, get_schemas
from suzieq.utils import get_query_output


@command('analyze', help="Analyze this")
class AnalyzeCommand:

    @argument("datacenter", description="datacenter to qualify selection")
    @argument("hostname", description="Name of host to qualify selection")
    @argument("start_time",
              description="Start of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("end_time",
              description="End of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("view", description="view all records or just the latest",
              choices=["all", "latest"])
    def __init__(self, hostname: typing.List[str] = [], start_time: str = '',
                 end_time: str = '', view: str = 'latest',
                 datacenter: typing.List[str] = []) -> None:
        self._cfg = load_sq_config(validate=False)
        self._schemas = get_schemas(self._cfg['schema-directory'])
        self.datacenter = datacenter
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
    '''Go deeper into the data'''

    @command('uplink-ratio')
    @argument("ifname", description="interface name to qualify show")
    @argument("dir", description="Tx or Rx", choices=['rx', 'tx'])
    def uplink_ratio(self, dir: str, ifname: typing.List[str] = None):
        '''
        Get interface bandwidth
        '''
        col_name = 'txBytes' if dir == 'tx' else 'rxBytes'

        ifname_str = '('
        if isinstance(ifname, str):
            ifname = [ifname]

        if isinstance(self.hostname, str):
            self.hostname = [self.hostname]

        for i, ele in enumerate(ifname):
            prefix = ' or ' if i else ''
            ifname_str += "{}ifname=='{}'".format(prefix, ele)

        ifname_str += ')'

        hostname_str = '('
        for i, ele in enumerate(self.hostname):
            prefix = ' or ' if i else ''
            hostname_str += "{}hostname=='{}'".format(prefix, ele)
        hostname_str += ')'

        qstr = ("select hostname, ifname, {}, timestamp from ifCounters "
                "where {} and {} order by hostname, ifname, timestamp"
                .format(col_name, hostname_str, ifname_str))

        df = get_query_output(qstr, self.cfg, self.schemas, self.start_time,
                              self.end_time, view='all')
        df['prevBytes'] = df.groupby(['hostname', 'ifname'])[col_name].shift(1)
        df['prevTime'] = df.groupby(['hostname', 'ifname'])['timestamp'].shift(1)

        for hele in self.hostname:
            dflist = []
            for iele in ifname:
                subdf = df.where((df['hostname'] == hele) &
                                 (df['ifname'] == iele))
                subdf = subdf.dropna()
                subdf[iele] = ((subdf[col_name].sub(subdf['prevBytes']) * 8)
                               / (subdf['timestamp'].sub(subdf['prevTime'])))
                subdf['timestamp'] = pd.to_datetime(subdf['timestamp'],
                                                    unit='ms')
                dflist.append(subdf.drop(columns=[col_name, 'ifname',
                                                  'prevBytes', 'prevTime']))

            for i, subdf in enumerate(dflist[1:]):
                newdf = pd.merge(dflist[0],
                                 dflist[1][['timestamp', ifname[i+1]]],
                                 on='timestamp', how='left')
            
            for iele in ifname[1:]:
                newdf['%s:%s'%(iele, ifname[0])] = newdf[iele]/newdf[ifname[0]]

            newdf = newdf.drop(columns=ifname)

            print(newdf.describe())

            
