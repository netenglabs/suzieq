
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
from suzieq.sqobjects.mlag import mlagObj


@command('mlag', help="Act on mlag data")
class MlagCmd(SqCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: str = '',
                 format: str = "", columns: str = 'default') -> None:
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, datacenter=datacenter,
                         format=format, columns=columns)
        self.mlagobj = mlagObj(context=self.ctxt)

    @command('show')
    def show(self):
        """
        Show mlag info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.mlagobj.get(hostname=self.hostname,
                              columns=self.columns,
                              datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if not df.empty and 'state' in df.columns:
            return self._gen_output(df.query('state != "disabled"'))
        else:
            return self._gen_output(df)

    @command('summarize')
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def describe(self, groupby: str = ''):
        """
        Summarize mlag info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.mlagobj.summarize(hostname=self.hostname,
                                    columns=self.columns,
                                    groupby=groupby.split(),
                                    datacenter=self.datacenter)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
                        

