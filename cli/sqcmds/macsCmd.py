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
from suzieq.sqobjects.macs import macsObj


@command("macs", help="Act on MAC Table data")
class macsCmd(SQCommand):
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
        self.macsobj = macsObj(context=self.ctxt)

    @command("show")
    @argument("vlan", description="VLAN ID to qualify")
    @argument("macaddr", description="MAC address ID to qualify")    
    def show(self, vlan: str = '', macaddr: str = ''):
        """
        Show MAC table info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.macsobj.get(
            hostname=self.hostname,
            vlan=vlan.split(),
            macaddr=macaddr.split(),
            columns=self.columns,
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)

    @command("summarize")
    @argument("vlan", description="VLAN ID to qualify")
    @argument("macaddr", description="MAC address ID to qualify")    
    @argument("groupby", description="Space separated list of fields to group by")
    def summarize(self, vlan: str = "", macaddr: str = '', groupby: str = ""):
        """
        Summarize MAC Table info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.macsobj.summarize(
            hostname=self.hostname,
            vlan=vlan.split(),
            macaddr=macaddr.split(),
            groupby=groupby.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
