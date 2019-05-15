#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
import time
import typing
from nubia import command, argument,  context
import pandas as pd

sys.path.append('/home/ddutt/work/')
from suzieq.cli.commands.command import SQCommand
from suzieq.sqobjects.ospf import ospfObj


@command('ospf', help="Act on OSPF data")
class ospfCmd(SQCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 columns: str = 'default') -> None:
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter, columns=columns)
        self.ospfobj = ospfObj(context=self.ctxt)

    @command('show')
    @argument("ifname",
              description="Space separated list of interface names to qualify")
    @argument("vrf",
              description="Space separated list of VRFs to qualify")
    @argument("state", description="BGP neighbor state to qualify",
              choices=["full"])
    @argument("type", description="Type of OSPF information to show",
              choices=["neighbor", "interface"])
    def show(self, ifname: str = '', vrf: str = '', state: str = '',
             type: str = 'neighbor'):
        """
        Show OSPF interface and neighbor info
        """
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.ospfobj.get(hostname=self.hostname,
                              vrf=vrf.split(),
                              ifname=ifname.split(),
                              state=state, columns=self.columns,
                              datacenter=self.datacenter,
                              type=type)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command('describe')
    @argument("ifname",
              description="Space separated list of interface names to qualify")
    @argument("vrf",
              description="Space separated list of VRFs to qualify")
    @argument("state", description="BGP neighbor state to qualify",
              choices=["full"])
    @argument("type", description="Type of OSPF information to show",
              choices=["neighbor", "interface"])
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def describe(self, ifname: str = '',
                 vrf: str = '', state: str = '',
                 type: str = 'neighbor', groupby: str = ''):
        """
        Describe OSPF data
        """
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.ospfobj.describe(hostname=self.hostname, vrf=vrf.split(),
                                   ifname=ifname.split(), state=state,
                                   columns=self.columns,
                                   datacenter=self.datacenter,
                                   type=type, groupby=groupby.split())
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command('assert')
    @argument("ifname", description="interface name to check OSPF on")
    @argument("vrf", description="VRF to assert OSPF state in")
    @argument("what", description="What do you want to assert about OSPF",
              choices=['all'])
    def aver(self, ifname: str = '', vrf: str = '',
             what: str = 'all') -> pd.DataFrame:
        """
        Test OSPF runtime state is good
        """
        now = time.time()
        result_df = self.ospfobj.aver(hostname=self.hostname, vrf=vrf.split(),
                                      ifname=ifname.split(),
                                      datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        if result_df.empty:
            print('Assert passed')
        else:
            print(result_df)
            print('Assert failed')

        return
        
