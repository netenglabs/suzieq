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
from suzieq.sqobjects.path import PathObj


@command("path", help="build and act on path data")
class PathCmd(SqCommand):
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
        self.pathobj = PathObj(context=self.ctxt)

    @command("show")
    @argument("src", description="show paths from")
    @argument("dest", description="show paths to")
    @argument("vrf", description="VRF to qualify")
    def show(self, src: str = "", dest: str = "", vrf: str = ''):
        """show paths between specified from source to target ip addresses"""
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.pathobj.get(
            hostname=self.hostname, columns=self.columns,
            datacenter=self.datacenter, source=src, dest=dest,
            vrf=vrf
        )

        if not df.empty:
            self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
            print(df)
