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
from suzieq.cli.lldp import lldpObj


@command('lldp', help="Act on LLDP data")
class lldpCmd(SQCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 columns: str = 'default') -> None:
        self.lldpobj = lldpObj()
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter, columns=columns)

    @command('show')
    @argument("ifname", description="interface name to qualify")
    def show(self, ifname: str = ''):
        """
        Show LLDP info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.lldpobj.get(hostname=self.hostname, ifname=ifname.split(),
                              columns=self.columns, datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command('describe')
    @argument("ifname", description="interface name to qualify")
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def describe(self, ifname: str = '', groupby: str = ''):
        """
        Describe LLDP info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.lldpobj.describe(hostname=self.hostname,
                                   ifname=ifname.split(),
                                   columns=self.columns,
                                   groupby=groupby.split(),
                                   datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
    

