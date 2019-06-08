#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import time
import typing
from nubia import command, argument, context
import pandas as pd

from suzieq.cli.sqcmds.command import SQCommand
from suzieq.sqobjects.arpnd import arpndObj


@command("arpnd", help="Act on ARP/ND data")
class arpndCmd(SQCommand):
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
        self.arpndobj = arpndObj(context=self.ctxt)

    @command("show")
    @argument("ipAddress", description="ipAddress to qualify")
    @argument("oif", description="outgoing interface to qualify")
    def show(self, ipAddress: str = "", oif: str = ''):
        """
        Show ARP/ND info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.arpndobj.get(
            hostname=self.hostname,
            ipAddress=ipAddress.split(),
            oif=oif.split(),
            columns=self.columns,
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command("summarize")
    @argument("ipAddress", description="ipAddress to qualify")
    @argument("oif", description="outgoing interface to qualify")
    @argument("groupby", description="Space separated list of fields to group by")
    def summarize(self, ipAddress: str = "", oif: str = '', groupby: str = ""):
        """
        Summarize ARP/ND info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.arpndobj.summarize(
            hostname=self.hostname,
            oif=oif.split(),
            ipAddress=ipAddress.split(),            
            columns=self.columns,
            groupby=groupby.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
