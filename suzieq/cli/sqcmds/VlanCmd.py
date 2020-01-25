
#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import time

from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.vlan import vlanObj


@command('vlan', help="Act on vlan data")
class VlanCmd(SqCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 columns: str = 'default') -> None:
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter, columns=columns)
        self.vlanobj = vlanObj(context=self.ctxt)

    @command('show')
    @argument("vlan", description="Space separated list of vlan IDs to show")
    def show(self, vlan: str = ''):
        """
        Show vlan info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.vlanobj.get(hostname=self.hostname, vlan=vlan,
                              columns=self.columns, datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
        return df

    @command('summarize')
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def summarize(self, groupby: str = ''):
        """
        Describe vlan info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.vlanobj.summarize(hostname=self.hostname,
                                    columns=self.columns,
                                    groupby=groupby.split(),
                                    datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
        return df


