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
from suzieq.sqobjects.routes import RoutesObj
from cyberpandas import IPNetworkType, IPNetworkArray, IPAccessor, to_ipnetwork


@command("routes", help="Act on Routes")
class RoutesCmd(SqCommand):
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
        self.routesobj = RoutesObj(context=self.ctxt)

    @command("show")
    @argument("prefix", description="Specific prefix to qualify")
    @argument("vrf", description="VRF to qualify")    
    def show(self, prefix: str = "", vrf: str = ''):
        """
        Show Routes info
        """
        if self.columns is None:
            return

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
        assert(df.size > 0)
        print(df)
        return df


    @command("summarize")
    @argument("prefix", description="Specific prefix to qualify")
    @argument("vrf", description="Specific VRF to qualify")
    @argument("groupby",
              description="space-separated list of fields to summarize")
    def summarize(self, prefix: str = "", vrf: str = '', groupby: str = ""):
        """
        Summarize Routing info
        """
        if self.columns is None:
            return

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
        return df

    @command('lpm')
    @argument("address", description="IP address for lpm")
    @argument("vrf", description="specific VRF to qualify")
    def lpm(self, address: str = "", vrf: str = "default"):
        """
        Show the Longest Prefix Match on a given prefix, vrf
        """
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        if not address:
            print('address is mandatory parameter')
            return

        df = self.routesobj.lpm(
            hostname=self.hostname,
            address=address,
            vrf=vrf.split(),
            columns=self.columns,
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        print(df)
        return df
