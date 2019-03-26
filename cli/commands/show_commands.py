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


@command('show', help="show various pieces of information")
class ShowCommand(SQCommand):
    '''Show Commands'''
    @command('system')
    @argument("vendor", description="vendor to qualify the output")
    @argument("os", description="OS to qualify the output")
    def show_system(self, vendor: typing.List[str] = None,
                    os: typing.List[str] = None) -> None:
        """
        Show BGP
        """
        order_by = 'order by datacenter, hostname, vendor'
        df = get_table_df('system', self.start_time, self.end_time,
                          self.view, order_by, self.cfg, self.schemas,
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
        order_by = 'order by datacenter, hostname, vrf, peer'
        df = get_table_df('bgp', self.start_time, self.end_time,
                          self.view, order_by, self.cfg, self.schemas,
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
        Show BGP
        """
        order_by = 'order by datacenter, hostname, vrf, ifname'
        if type == 'neighbor':
            df = get_table_df('ospfNbr', self.start_time, self.end_time,
                              self.view, order_by, self.cfg, self.schemas,
                              hostname=self.hostname, vrf=vrf, ifname=ifname,
                              state=state, datacenter=self.datacenter)
        else:
            df = get_table_df('ospfIf', self.start_time, self.end_time,
                              self.view, order_by, self.cfg, self.schemas,
                              hostname=self.hostname, vrf=vrf, ifname=ifname,
                              state=state, datacenter=self.datacenter)
        print(df)

    @command('interfaces')
    @argument("ifname", description="interface name to qualify show")
    def show_interfaces(self, ifname: typing.List[str] = None):
        """
        Show interfaces
        """
        # Get the default display field names
        order_by = 'order by hostname, ifname'
        df = get_table_df('interfaces', self.start_time, self.end_time,
                          self.view, order_by, self.cfg, self.schemas,
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
        order_by = 'order by hostname, ifname'
        df = get_table_df('lldp', self.start_time, self.end_time,
                          self.view, order_by, self.cfg, self.schemas,
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
        order_by = 'order by hostname, mountPoint'
        df = get_table_df('fs', self.start_time, self.end_time,
                          self.view, order_by, self.cfg, self.schemas,
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
        start = time.time()
        df = get_ifbw_df(self.datacenter, self.hostname, ifname, columns,
                         self.start_time, self.end_time, self.cfg,
                         self.schemas)

        print(df)
        print('Query executed in: {}s'.format(time.time() - start))

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


