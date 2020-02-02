#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

from collections import OrderedDict
import sys

import pandas as pd
import numpy as np
import typing

from suzieq.sqobjects import interfaces, lldp, routes, arpnd, macs, basicobj


# TODO: Handle EVPN
# TODO: Handle MLAG
class pathObj(basicobj.SQObject):
    def __init__(
        self,
        engine: str = "",
        hostname: typing.List[str] = [],
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        datacenter: typing.List[str] = [],
        columns: typing.List[str] = ["default"],
        context=None,
    ) -> None:
        super().__init__(
            engine,
            hostname,
            start_time,
            end_time,
            view,
            datacenter,
            columns,
            context=context,
            table=None,
        )
        self._sort_fields = ["datacenter", "hostname", "pathid"]
        self._cat_fields = []

    def _get_fhr(self, datacenter: str, ipaddr: str, if_df):
        """Identify the first hop router to a given IP address"""

        arp_df = arpnd.arpndObj().get(datacenter=[datacenter],
                                      ipAddress=ipaddr)
        if arp_df.empty:
            raise AttributeError(
                "Cannot obtain IP/LLDP neighbor info for " "address {}"
                .format(ipaddr)
            )

        macaddr = arp_df.iloc[0]["macaddr"]  # same macaddr across entries
        oif = arp_df.iloc[0]["oif"]
        tmphost = arp_df.iloc[0]["hostname"]  # TODO: server MLAG bond

        # This is to handle the VRR interface on Cumulus Linux machines
        if oif.endswith("-v0"):
            oif = oif.split("-v0")[0]

        oif_df = if_df[(if_df["hostname"] == tmphost) &
                       (if_df["ifname"] == oif)]

        if oif_df.empty:
            raise AttributeError(
                "Cannot obtain IP/LLDP neighbor info for " "address {}"
                .format(ipaddr)
            )

        vlan = oif_df.iloc[0]["vlan"]
        if macaddr:
            mac_df = macs.macsObj().get(
                datacenter=[datacenter], macaddr=macaddr, vlan=vlan
            )
            if not mac_df.empty:
                mac_df = mac_df[mac_df["remoteVtepIp"] == ""]

            if mac_df.empty:
                raise AttributeError(
                    "Cannot obtain IP/LLDP neighbor info for "
                    "address {}".format(ipaddr)
                )
            vrf = oif_df['master'].iloc[-1].strip()
            if not vrf or (vrf == "bridge"):
                vrf = 'default'
            return OrderedDict(
                {
                    key: {"iif": value,
                          "mtu": oif_df['mtu'].iloc[-1],
                          "overlay": False,
                          'vrf': vrf}
                    for key, value in zip(
                        mac_df["hostname"].tolist(), mac_df["oif"].tolist()
                    )
                }
            )
        return OrderedDict({})

    def trace(self, **kwargs) -> pd.DataFrame:
        """return a pandas dataframe with the paths between src and dest"""

        if not self.ctxt.engine:
            raise AttributeError(
                "Specify an analysis engine using set engine " "command"
            )
            return pd.DataFrame(columns=["datacenter", "hostname"])

        datacenter = kwargs.get("datacenter", self.ctxt.datacenter)
        source = kwargs.get("source", None)
        target = kwargs.get("target", None)
        vrf = kwargs.get("vrf", "default")

        if not source or not target:
            raise AttributeError("Must specify trace source and target")

        if_df = interfaces.ifObj().get(datacenter=[datacenter])
        src_df = if_df[if_df.ipAddressList.astype(str)
                       .str.contains(source + "/")]
        tgt_df = if_df[if_df.ipAddressList.astype(str)
                       .str.contains(target + "/")]
        tgt_host = tgt_df["hostname"].unique()[0]
        src_host = src_df["hostname"].unique()[0]
        lldp_df = lldp.lldpObj().get(datacenter=[datacenter])
        rdf = routes.routesObj().lpm(datacenter=[datacenter], address=target)

        if lldp_df[lldp_df["hostname"] == src_host].empty:
            hosts_iifs = self._get_fhr(datacenter, source, if_df)
        else:
            hosts_iifs = OrderedDict(
                {
                    src_host: {
                        "iif": src_df["ifname"].unique()[0],
                        "mtu": src_df["mtu"].unique()[0],
                        "overlay": False
                    }
                }
            )

        if lldp_df[lldp_df["hostname"] == tgt_host].empty:
            # The target node has no LLDP data, so find prev node to end
            tgt_host_iifs = self._get_fhr(datacenter, target, if_df)
        else:
            tgt_host_iifs = OrderedDict(
                {
                    tgt_host: {
                        "iif": tgt_df["ifname"].unique()[0],
                        "vrf": tgt_df["master"].unique()[0] or "default",
                        "mtu": tgt_df["mtu"].unique()[0],
                        "overlay": False
                    }
                }
            )

        paths = [[hosts_iifs]]
        visited_hosts = set()

        # The logic is to loop through the nexthops till you reach the target
        # host The topmost while is this looping. The next loop within handles
        # one nexthop at a time.The paths are constructed as a list of lists,
        # where each element of the outermost loop is one complete path and
        # each inner list represents one hop in that path. Each hop is the
        # list of hostname and incoming interface. loops are detected by
        # ensuring that no host is visited twice in the same VRF. The VRF
        # qualification is required to ensure packets coming back from a
        # firewall or load balancer are tagged as duplicates.

        while hosts_iifs:
            nexthosts_iifs = OrderedDict()
            newpaths = []
            hosts_this_round = set()

            for host in hosts_iifs:
                iif = hosts_iifs[host]["iif"]
                ivrf = None
                if iif:
                    ivrf = (
                        if_df[(if_df["hostname"] == host) &
                              (if_df["ifname"] == iif)]["master"]
                        .to_string(index=False)
                        .strip()
                    )
                # Cumulus hack to avoid markind bridged bond interfaces as vrf
                if not ivrf or ivrf == "bridge":
                    ivrf = dvrf

                hosts_iifs[host]["vrf"] = ivrf
                skey = host + ivrf

                if skey in visited_hosts:
                    # This is a loop
                    raise AttributeError("Loop detected on node {}"
                                         .format(host))
                hosts_this_round.add(skey)

                if host in tgt_host_iifs:
                    continue
                rslt = rdf.query('hostname == "{}" and vrf == "{}"'
                                 .format(host, ivrf))
                if rslt.empty:
                    continue
                oifs = rslt.oifs.iloc[0].tolist()

                newhosts_iifs = {}
                for iface in oifs:
                    vlan = 0
                    # Remove VLAN subinterfaces
                    if "." in iface:
                        raw_iface, vlan = iface.split(".")
                    else:
                        raw_iface = iface

                    raw_iface = [raw_iface]
                    # Replace bonds with their individual ports
                    slaveoifs = if_df[
                        (if_df["hostname"] == host)
                        & (if_df["master"] == raw_iface[0])
                    ].ifname.tolist()

                    if slaveoifs:
                        raw_iface = slaveoifs

                    # We need only one of the interfaces (multiple entries
                    # here are only in case of a bond
                    # TODO: This will not be true with MLAG
                    df = lldp_df[
                        (lldp_df["hostname"] == host)
                        & (lldp_df["ifname"] == raw_iface[0])
                    ]

                    if df.empty:
                        continue

                    peer_host = df["peerHostname"].to_string(index=False).strip()
                    peer_if = df["peerIfname"].to_string(index=False).strip()

                    if slaveoifs:
                        peer_if_master = (
                            if_df[
                                (if_df["hostname"] == peer_host)
                                & (if_df["ifname"] == peer_if)
                            ]["master"]
                            .to_string(index=False)
                            .strip()
                        )
                        if peer_if_master:
                            peer_if = peer_if_master

                    if vlan:
                        peer_if += ".{}".format(vlan)

                    mtu_match = (
                        if_df[
                            (if_df["hostname"] == peer_host)
                            & (if_df["ifname"] == peer_if)
                        ]
                        .iloc[-1]
                        .mtu
                        == if_df[
                            (if_df["hostname"] == host)
                            & (if_df["ifname"] == iface)
                        ]
                        .iloc[-1]
                        .mtu
                    )

                    newhosts_iifs[peer_host] = {
                        "iif": peer_if,
                        "vrf": ivrf,
                        "overlay": False,
                        "mtu": if_df[
                            (if_df["hostname"] == peer_host)
                            & (if_df["ifname"] == peer_if)
                        ]
                        .iloc[-1]
                        .mtu,
                        "mtu_match": mtu_match,
                    }

                if not newhosts_iifs:
                    break

                for x in paths:
                    if x[-1].keys().isdisjoint([host]):
                        continue
                    for y in newhosts_iifs:
                        z = x + [OrderedDict({y: newhosts_iifs[y]})]
                        if z not in newpaths:
                            newpaths.append(z)

                for x in newhosts_iifs:
                    if x not in nexthosts_iifs:
                        nexthosts_iifs[x] = newhosts_iifs[x]

            if newpaths:
                paths = newpaths

            visited_hosts = visited_hosts.union(hosts_this_round)
            hosts_iifs = nexthosts_iifs

        # Add the final destination to all paths
        for path in paths:
            path.append(tgt_host_iifs)
        return paths


if __name__ == "__main__":
    import pprint

    datacenter = sys.argv[1]
    source = sys.argv[2]
    target = sys.argv[3]
    dvrf = sys.argv[4]

    tpobj = pathObj()
    paths = tpobj.trace(datacenter=datacenter, source=source, target=target,
                        vrf=dvrf)

    # Construct Pandas DataFrame
    df_plist = []
    for i, path in enumerate(paths):
        for j, ele in enumerate(path):
            item = list(ele)[0]
            df_plist.append(
                {
                    "pathid": i + 1,
                    "stageid": j + 1,
                    "datacenter": datacenter,
                    "hostname": item,
                    "iif": ele[item]["iif"],
                    "vrf": ele[item]["vrf"],
                    "overlay": ele[item]["overlay"],
                    "mtu_match": ele[item].get("mtu_match", np.nan),
                    "mtu": ele[item].get("mtu", 0),
                }
            )
    df = pd.DataFrame(df_plist)
    print(df)
