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
import time

import pandas as pd
from termcolor import cprint
from nubia import command, argument, context
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.utils import get_table_df, get_ifbw_df
from suzieq.cli.commands.command import SQCommand
from suzieq.pdutils import pd_get_table_df


@command('show', help="show various pieces of information")
class ShowCommand(SQCommand):
    '''Show Commands'''

    def _show_run(self, table, sort_fields, **kwargs):
        '''Workshorse show command'''

        now = time.time()
        if self.ctxt.engine == 'spark':
            df = get_table_df(table, self.start_time, self.end_time, self.view,
                              sort_fields, self.cfg, self.schemas, **kwargs)
        else:
            df = pd_get_table_df(table, self.start_time, self.end_time,
                                 self.view, sort_fields, self.cfg,
                                 self.schemas, **kwargs)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms',
                                             cache=True)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return(df)

    @command('system')
    @argument("vendor", description="vendor to qualify the output")
    @argument("os", description="OS to qualify the output")
    def show_system(self, vendor: typing.List[str] = None,
                    os: typing.List[str] = None) -> None:
        """
        Show BGP
        """
        sort_fields = ['datacenter', 'hostname', 'vendor']
        df = self._show_run('system', sort_fields,
                            hostname=self.hostname, vendor=vendor, os=os,
                            datacenter=self.datacenter)

        df['bootupTimestamp'] = (pd.to_datetime(df['timestamp']) -
                                 pd.to_datetime(df['bootupTimestamp'],
                                                unit='s'))
        print(df)

    @command('bgp')
    @argument("peer", description="Name of peer to qualify show")
    @argument("vrf", description="VRF to qualify show")
    @argument("state", description="BGP neighbor state to qualify",
              choices=["Established", "NotEstd"])
    def show_bgp(self, peer: typing.List[str] = None,
                 vrf: typing.List[str] = None, state: str = ''):
        """
        Show BGP
        """
        sort_fields = ['datacenter', 'hostname', 'vrf', 'peer']
        df = self._show_run('bgp', sort_fields,
                            hostname=self.hostname, vrf=vrf, peer=peer,
                            state=state, datacenter=self.datacenter)
        print(df)

    @command('ospf')
    @argument("ifname", description="Name of interface to qualify show")
    @argument("vrf", description="VRF to qualify show")
    @argument("state", description="BGP neighbor state to qualify",
              choices=["full"])
    @argument("type", description="Type of OSPF information to show",
              choices=["neighbor", "interface"])
    def show_ospf(self, ifname: typing.List[str] = None,
                  vrf: typing.List[str] = None, state: str = '',
                  type: str = 'neighbor'):
        """
        Show OSPF info
        """
        now = time.time()
        sort_fields = ['datacenter', 'hostname', 'vrf', 'ifname']
        if type == 'neighbor':
            table = 'ospfNbr'
        else:
            table = 'ospfIf'

        df = self._show_run(table, sort_fields,
                            hostname=self.hostname, vrf=vrf,
                            ifname=ifname, state=state,
                            datacenter=self.datacenter)
        print(df)

    @command('interfaces')
    @argument("ifname", description="interface name to qualify show")
    def show_interfaces(self, ifname: typing.List[str] = None):
        """
        Show interfaces
        """
        # Get the default display field names
        sort_fields = ['hostname', 'ifname']
        df = self._show_run('interfaces', sort_fields,
                            hostname=self.hostname, ifname=ifname,
                            datacenter=self.datacenter)
        print(df)

    @command('lldp')
    @argument("ifname", description="interface name to qualify show")
    def show_lldp(self, ifname: typing.List[str] = None):
        """
        Show LLDP info
        """
        # Get the default display field names
        sort_fields = ['hostname', 'ifname']
        df = self._show_run('lldp', sort_fields,
                            hostname=self.hostname, ifname=ifname,
                            datacenter=self.datacenter)
        print(df)

    @command('filesystem')
    @argument("mountPoint", description="Mountpoint to filter by")
    @argument("usedPercent", description="show only if used percentage is >=")
    def show_fs(self, mountPoint: str = None, usedPercent: str = None):
        """
        Show filesystem info
        """
        # Get the default display field names
        sort_fields = ['hostname', 'mountPoint']
        df = self._show_run('fs', sort_fields,
                            hostname=self.hostname, mountPoint=mountPoint,
                            usedPercent=usedPercent,
                            datacenter=self.datacenter)
        print(df)

    @command('ifbw')
    @argument("ifname", description="interface name to qualify show")
    def show_ifbw(self, ifname: typing.List[str] = None):
        """
        Show interface bandwidth for given host/ifname
        """
        # Get the default display field names
        columns = ['txBytes', 'txPackets', 'rxBytes', 'rxPackets']
        now = time.time()
        df = get_ifbw_df(self.datacenter, self.hostname, ifname, columns,
                         self.start_time, self.end_time, self.cfg,
                         self.schemas)

        print(df)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

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


