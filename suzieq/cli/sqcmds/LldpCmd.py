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

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.lldp import LldpObj


@command("lldp", help="Act on LLDP data")
class LldpCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        datacenter: str = "",
        format: str = "",
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
            format=format,
            sqobj=LldpObj,
        )

    @command("show")
    @argument("ifname", description="interface name to qualify")
    def show(self, ifname: str = ""):
        """
        Show LLDP info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.sqobj.get(
            hostname=self.hostname,
            ifname=ifname.split(),
            columns=self.columns,
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    @argument("ifname", description="interface name to qualify")
    @argument("groupby", description="Space separated list of fields to summarize on")
    def summarize(self, ifname: str = "", groupby: str = ""):
        """
        Summarize LLDP info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.sqobj.summarize(
            hostname=self.hostname,
            ifname=ifname.split(),
            columns=self.columns,
            groupby=groupby.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
