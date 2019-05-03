
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

sys.path.append('/home/ddutt/work/')
from suzieq.cli.commands.command import SQCommand
from suzieq.cli.system import systemObj


@command('system', help="Act on LLDP data")
class systemCmd(SQCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 columns: str = 'default') -> None:
        self.systemobj = systemObj()
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter, columns=columns)

    @command('show')
    def show(self):
        """
        Show system info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.systemobj.get(hostname=self.hostname, 
                                columns=self.columns,
                                datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command('describe')
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def describe(self, groupby: str = ''):
        """
        Describe system info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.systemobj.describe(hostname=self.hostname,
                                     columns=self.columns,
                                     groupby=groupby.split(),
                                     datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
    

