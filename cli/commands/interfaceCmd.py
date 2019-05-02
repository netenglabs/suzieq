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
from suzieq.cli.interface import ifObj


@command('interface', help="Act on Interface data")
class ifCmd(SQCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 columns: str = 'default') -> None:
        self.ifobj = ifObj()
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter, columns=columns)

    @command('show')
    @argument("ifname", description="interface name to qualify")
    @argument("state", description="interface state to qualify show",
              choices=['up', 'down'])
    def show(self, ifname: str = '', state: str = ''):
        """
        Show interface info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.ifobj.get(hostname=self.hostname, ifname=ifname.split(),
                            columns=self.columns, datacenter=self.datacenter,
                            state=state)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command('describe')
    @argument("ifname", description="interface name to qualify")
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def describe(self, ifname: str = '', groupby: str = ''):
        """
        Describe interface info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.ifobj.describe(hostname=self.hostname, ifname=ifname.split(),
                                 columns=self.columns, groupby=groupby.split(),
                                 datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command('assert')
    @argument("ifname", description="interface name to qualify")
    @argument("what", description="What do you want to assert",
              choices=['mtu-match', 'mtu-value'])
    @argument("value", description="Value to match against")
    def aver(self, ifname: str = '', state: str = '',
             what: str = 'mtu-match', value: int = 0):
        """
        Assert aspects about the interface
        """
        now = time.time()

        if what == 'mtu-value' and value == 0:
            print('Provide value to match MTU against')
            return

        df = self.ifobj.aver(hostname=self.hostname, ifname=ifname.split(),
                             columns=self.columns, datacenter=self.datacenter,
                             what=what, matchval=value)
        if df.empty:
            print('Assert passed')
        else:
            print(df)
            print('Assert failed')

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return


