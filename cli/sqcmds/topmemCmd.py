
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
from suzieq.cli.sqcmds.command import SQCommand
from suzieq.sqobjects.topmem import topmemObj


@command('topmem', help="Act on LLDP data")
class topmemCmd(SQCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 columns: str = 'default') -> None:
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter, columns=columns)
        self.topmemobj = topmemObj(context=self.ctxt)

    @command('show')
    def show(self):
        """
        Show topmem info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.topmemobj.get(hostname=self.hostname, 
                                columns=self.columns,
                                datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command('describe')
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def describe(self, groupby: str = ''):
        """
        Describe topmem info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.topmemobj.describe(hostname=self.hostname,
                                     columns=self.columns,
                                     groupby=groupby.split(),
                                     datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

