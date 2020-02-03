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
from suzieq.sqobjects.system import SystemObj


@command("system", help="Act on system data")
class SystemCmd(SqCommand):
    """system command"""
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
        self.systemobj = SystemObj(context=self.ctxt)

    @command("show", help="Show system information")
    def show(self):
        """
        Show system info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.systemobj.get(
            hostname=self.hostname, columns=self.columns,
            datacenter=self.datacenter
        )
        # Convert the bootup timestamp into a time delta
        if not df.empty and 'bootupTimestamp' in df.columns:
            uptime_cols = (df['timestamp'] -
                           pd.to_datetime(df['bootupTimestamp']*1000,
                                          unit='ms'))
            uptime_cols = pd.to_timedelta(uptime_cols, unit='ms')
            df.insert(len(df.columns)-1, 'uptime', uptime_cols)
            self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
            print(df.drop(columns=['bootupTimestamp']))
        else:
            self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
            print(df)

    @command("summarize", help="Summarize system information")
    @argument("groupby", description="Space separated list of fields to summarize on")
    def summarize(self, groupby: str = ""):
        """
        Summarize system info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.systemobj.summarize(
            hostname=self.hostname,
            columns=self.columns,
            groupby=groupby.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
