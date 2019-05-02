#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
import time

from nubia import command, argument
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.cli.commands.command import SQCommand
from suzieq.cli.ospf import OspfObj


@command('ospf', help="Act on OSPF data")
class OspfCmd(SQCommand):


    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 columns: str = 'default') -> None:
        self.ospfobj = OspfObj()
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter, columns=columns)

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
