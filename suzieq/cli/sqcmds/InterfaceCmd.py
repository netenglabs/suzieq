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
from suzieq.sqobjects.interfaces import IfObj


@command("interface", help="Act on Interface data")
class InterfaceCmd(SqCommand):
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
            sqobj=IfObj
        )

    @command("show")
    @argument("ifname", description="interface name to qualify")
    @argument("type", description="interface type to qualify")
    @argument("state", description="interface state to qualify show",
              choices=["up", "down"])
    def show(self, ifname: str = "", state: str = "", type: str = ""):
        """
        Show interface info
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
            state=state,
            type=type.split(),
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    @argument("ifname", description="interface name to qualify")
    @argument("groupby",
              description="Space separated list of fields to summarize on")
    def summarize(self, ifname: str = "", groupby: str = ""):
        """
        Describe interface info
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

    @command("assert")
    @argument("ifname", description="interface name to qualify")
    @argument(
        "what",
        description="What do you want to assert",
        choices=["mtu-match", "mtu-value"],
    )
    @argument("value", description="Value to match against")
    def aver(self, ifname: str = "", state: str = "", what: str = "mtu-match",
             value: int = 0):
        """
        Assert aspects about the interface
        """
        if self.columns is None:
            return

        now = time.time()

        if what == "mtu-value" and value == 0:
            print("Provide value to match MTU against")
            return

        if what == "mtu-match":
            value = 0
        df = self.sqobj.aver(
            hostname=self.hostname,
            ifname=ifname.split(),
            columns=self.columns,
            datacenter=self.datacenter,
            what=what,
            matchval=value,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if df.empty:
            print("Assert passed")
        else:
            print(df)
            print("Assert failed")

        return df

    @command("top")
    @argument("what", description="Field you want to see top for",
              choices=["transitions"])
    @argument("count", description="How many top entries")
    def top(self, what: str = "transitions", count: int = 5):
        """
        Show top n entries based on specific field
        """
        if self.columns is None:
            return

        now = time.time()

        df = self.sqobj.top(
            hostname=self.hostname,
            what=what,
            n=count,
            columns=self.columns,
            datacenter=self.datacenter,
        )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
