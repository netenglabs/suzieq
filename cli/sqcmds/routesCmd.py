#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SQCommand
from suzieq.sqobjects.routes import routesObj


@command("routes", help="Act on Routes")
class routesCmd(SQCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        datacenter: str = "",
        columns: str = "default",
    ) -> None:
        super().__init__(
            engine=engine,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
            view=view,
            datacenter=datacenter,
            columns=columns,
        )
        self.routesobj = routesObj(context=self.ctxt)

    @command("show")
    @argument("prefix", description="Specific prefix to qualify")
    @argument("vrf", description="VRF to qualify")    
    def show(self, prefix: str = "", vrf: str = ''):
        """
        Show Routes info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.routesobj.get(
            hostname=self.hostname,
            prefix=prefix.split(),
            vrf=vrf.split(),
            columns=self.columns,
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command("summarize")
    @argument("prefix", description="Specific prefix to qualify")
    @argument("vrf", description="Specific VRF to qualify")    
    @argument("groupby", description="Space separated list of fields to summarize on")
    def summarize(self, prefix: str = "", vrf: str = '', groupby: str = ""):
        """
        Summarize Routing info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.routesobj.summarize(
            hostname=self.hostname,
            prefix=prefix.split(),
            vrf=vrf.split(),            
            columns=self.columns,
            groupby=groupby.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
