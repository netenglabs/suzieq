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
from suzieq.sqobjects.arpnd import ArpndObj


@command("arpnd", help="Act on ARP/ND data")
class ArpndCmd(SqCommand):
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
        )
        self.arpndobj = ArpndObj(context=self.ctxt)

    @command("show")
    @argument("address", description="IP address to qualify")
    @argument("oif", description="outgoing interface to qualify")
    def show(self, address: str = "", oif: str = ''):
        """
        Show ARP/ND info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.arpndobj.get(
            hostname=self.hostname,
            ipAddress=address.split(),
            oif=oif.split(),
            columns=self.columns,
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    @argument("address", description="IP address to qualify")
    @argument("oif", description="outgoing interface to qualify")
    @argument("groupby", description="Space separated list of fields to group by")
    def summarize(self, address: str = "", oif: str = '', groupby: str = ""):
        """
        Summarize ARP/ND info
        """

        if self.columns is None:
            return
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.arpndobj.summarize(
            hostname=self.hostname,
            oif=oif.split(),
            ipAddress=address.split(),
            columns=self.columns,
            groupby=groupby.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
