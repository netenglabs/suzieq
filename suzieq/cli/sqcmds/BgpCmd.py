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
from suzieq.sqobjects.bgp import bgpObj


@command("bgp", help="Act on BGP data")
class BgpCmd(SqCommand):
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
        self.bgpobj = bgpObj(context=self.ctxt)

    @command("show")
    def show(self):
        """
        Show bgp info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.bgpobj.get(
            hostname=self.hostname, columns=self.columns, datacenter=self.datacenter
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command("summarize")
    @argument("groupby", description="Space separated list of fields to summarize on")
    def summarize(self, groupby: str = ""):
        """
        Summarize bgp info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.bgpobj.summarize(
            hostname=self.hostname,
            columns=self.columns,
            groupby=groupby.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
