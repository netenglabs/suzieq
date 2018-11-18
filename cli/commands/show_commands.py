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

sys.path.append('/home/ddutt/work/')
from suzieq.livylib import get_livysession, exec_livycode
from suzieq.utils import load_sq_config, get_schemas
from suzieq.utils import get_spark_code, get_query_output


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
              choices=["all", "latest"])
    def __init__(self, hostname: str = None, start_time: str = '',
                 end_time: str = '', view: str = 'latest') -> None:
        self._cfg = load_sq_config(validate=False)
        self._schemas = get_schemas(self._cfg['schema-directory'])
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
    @argument("state", description="BGP neighbor state to qualify",
              choices=["Established", "NotEstd"])
    def show_bgp(self, peer: str = None, vrf: str = None, state:str = ''):
        """
        Show BGP
        """
        order_by = 'order by hostname, vrf, peer'
        df = self.get_table_df('bgp', self.start_time, self.end_time,
                               self.view, order_by,
                               hostname=self.hostname, vrf=vrf, peer=peer,
                               state=state)
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


