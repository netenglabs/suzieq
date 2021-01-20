from ipaddress import ip_network, ip_address
from collections import OrderedDict
from itertools import repeat
from functools import lru_cache
from collections import defaultdict
from copy import copy

import numpy as np
import pandas as pd

from suzieq.sqobjects import interfaces, routes, arpnd, macs, mlag
from suzieq.exceptions import EmptyDataframeError, PathLoopError
from suzieq.engines.pandas.engineobj import SqEngineObject
from suzieq.utils import expand_nxos_ifname, MAX_MTU

# TODO: What timestamp to use (arpND, mac, interface, route..)


class PathObj(SqEngineObject):

    def _init_dfs(self, namespace, source, dest):
        """Initialize the dataframes used in this path hunt"""

        self.source = source
        self.dest = dest
        self._underlay_dfs = {}  # lpm entries for each vtep IP

        try:
            self._if_df = interfaces.IfObj(context=self.ctxt) \
                                    .get(namespace=namespace, state='up',
                                         addnl_fields=['macaddr']) \
                                    .explode('ipAddressList') \
                                    .fillna({'ipAddressList': ''}) \
                                    .explode('ip6AddressList') \
                                    .fillna({'ip6AddressList': ''}) \
                                    .reset_index(drop=True)
            if self._if_df.empty:
                raise EmptyDataframeError
        except (EmptyDataframeError, KeyError):
            raise EmptyDataframeError(
                f"No interface information found for {namespace}")

        # Need this in determining L2 peer
        mlag_df = mlag.MlagObj(context=self.ctxt).get(namespace=namespace)
        mlag_peers = defaultdict(str)
        mlag_peerlink = defaultdict(str)
        if not mlag_df.empty:
            peerlist = [x.tolist()
                        for x in mlag_df.groupby(by=['systemId'])['hostname']
                        .unique().tolist()]
            for peers in peerlist:
                mlag_peers[peers[0]] = peers[1]
                mlag_peers[peers[1]] = peers[0]
            for row in mlag_df.itertuples():
                mlag_peerlink[row.hostname] = expand_nxos_ifname(row.peerLink)
        self._mlag_peers = mlag_peers
        self._mlag_peerlink = mlag_peerlink

        try:
            # access-internal is an internal Junos route we want to
            # ignore
            self._rdf = routes.RoutesObj(context=self.ctxt) \
                              .lpm(namespace=namespace, address=dest) \
                              .query('protocol != "access-internal"') \
                              .reset_index(drop=True)
            if self._rdf.empty:
                raise EmptyDataframeError
        except (KeyError, EmptyDataframeError):
            raise EmptyDataframeError("No Routes information found for {}".
                                      format(dest))

        try:
            self._rpf_df = routes.RoutesObj(context=self.ctxt) \
                                 .lpm(namespace=namespace, address=source) \
                                 .query('protocol != "access-internal"') \
                                 .reset_index(drop=True)
            if self._rpf_df.empty:
                raise EmptyDataframeError
        except (KeyError, EmptyDataframeError):
            raise EmptyDataframeError("No Routes information found for {}".
                                      format(source))

        # We ignore the lack of ARPND for now
        self._arpnd_df = arpnd.ArpndObj(
            context=self.ctxt).get(namespace=namespace)
        if self._arpnd_df.empty:
            raise EmptyDataframeError(
                f"No ARPND information found for {dest}")

        # Enhance the ARPND table with the VRF field
        self._arpnd_df = self._arpnd_df.merge(
            self._if_df[['namespace', 'hostname', 'ifname', 'master']],
            left_on=['namespace', 'hostname', 'oif'],
            right_on=['namespace', 'hostname', 'ifname'], how='left') \
            .drop(columns=['ifname']) \
            .rename(columns={'master': 'vrf'}) \
            .replace({'vrf': {'': 'default'}}) \
            .query('state != "failed"') \
            .reset_index(drop=True)

        self._macsobj = macs.MacsObj(context=self.ctxt, namespace=namespace)

        if ':' in source:
            self._src_df = self._if_df[self._if_df.ip6AddressList.astype(str)
                                       .str.contains(source + "/")]
        else:
            self._src_df = self._if_df[self._if_df.ipAddressList.astype(str)
                                       .str.contains(source + "/")]

        if self._src_df.empty:
            # TODO: No host with this src addr. Is addr a local ARP entry?
            self._src_df = self._find_fhr_df(None, source)

        if self._src_df.empty:
            raise AttributeError(f"Invalid src {source}")

        if self._src_df.hostname.nunique() == 1 and len(self._src_df) > 1:
            # Multiple interfaces with the same IP address. Possible case
            # of Unnumbered interfaces. See if there's a loopback in there
            if 'loopback' in self._src_df.type.unique().tolist():
                self._src_df = self._src_df.query('type == "loopback"')

        if ':' in dest:
            self._dest_df = self._if_df[self._if_df.ip6AddressList.astype(str)
                                        .str.contains(dest + "/")]
        else:
            self._dest_df = self._if_df[self._if_df.ipAddressList.astype(str)
                                        .str.contains(dest + "/")]

        srcnet = self._src_df.ipAddressList.tolist()[0]
        if ip_address(dest) in ip_network(srcnet, strict=False):
            self.is_l2 = True
        else:
            self.is_l2 = False

        if self._dest_df.empty:
            # TODO: No host with this dest addr. Is addr a local ARP entry?
            self._dest_df = self._find_fhr_df(None, dest)

        if self._dest_df.empty:
            raise AttributeError(f"Invalid dest {dest}")

        if self._dest_df.hostname.nunique() == 1 and len(self._dest_df) > 1:
            # Multiple interfaces with the same IP address. Possible case
            # of Unnumbered interfaces. See if there's a loopback in there
            if 'loopback' in self._dest_df.type.unique().tolist():
                self._dest_df = self._dest_df.query('type == "loopback"')

        self.dest_device = self._dest_df["hostname"].unique()
        self.src_device = self._src_df["hostname"].unique()

        # Start with the source host and find its route to the destination
        if self._rdf[self._rdf["hostname"].isin(self.src_device)].empty:
            raise EmptyDataframeError(f"No routes found for {self.src_device}")

    def _get_vrf(self, hostname: str, ifname: str, addr: str) -> str:
        """Determine the VRF given either the ifname or ipaddr"""
        vrf = ''
        if addr and ':' in addr:
            ipvers = 6
        else:
            ipvers = 4
        if ifname:
            iifdf = self._if_df[(self._if_df["hostname"] == hostname) &
                                (self._if_df["ifname"] == ifname)]
        else:
            # TODO: Add support for IPv6 here
            addr = addr + '/'
            if ipvers == 6:
                iifdf = self._if_df.query(
                    f'hostname=="{hostname}" and '
                    f'ip6AddressList.str.startswith("{addr}")')
            else:
                iifdf = self._if_df.query(
                    f'hostname=="{hostname}" and '
                    f'ipAddressList.str.startswith("{addr}")')
        if not iifdf.empty and iifdf.iloc[0].master == "bridge":
            # OK, find the SVI associated with this interface
            if addr and ipvers == 6:
                iifdf = self._if_df.query(
                    f'hostname=="{hostname}" and '
                    f'ip6AddressList.str.startswith("{addr}")')
            elif addr and ipvers == 4:
                iifdf = self._if_df.query(
                    f'hostname=="{hostname}" and '
                    f'ipAddressList.str.startswith("{addr}")')
            else:
                # No address, but a bridge interface as the master
                if iifdf.iloc[0]['vlan']:
                    # Check if there's an SVI, assuming format is vlan*
                    # TODO: Handle trunk
                    vlan = iifdf.iloc[0]['vlan']
                    vdf = self._if_df.query(f'hostname=="{hostname}" and '
                                            f'(ifname=="vlan{vlan}" or '
                                            f'ifname=="Vlan{vlan}")')
                    if not vdf.empty:
                        vrf = vdf.iloc[0].master.strip()

        if not iifdf.empty and not vrf:
            vrf = iifdf.iloc[0].master.strip()
            if vrf == "bridge":
                vrf = ''

        return vrf

    def _find_fhr_df(self, device: str, ip: str) -> pd.DataFrame:
        """Find Firstt Hop Router's iface DF for a given IP and device.
        The logic in finding the next hop router is:
          find the arp table entry corresponding to the IP provided;
          if this result is empty or the MAC addr is not unique:
             return null;
          extract unique MAC and search MAC table for this MAC;
          if the MAC table search is empty:
             return null;
          concat the dataframe using every row of the MAC DF to find if_df
          Return the concat if_df as FHR
        """
        fhr_df = pd.DataFrame()
        if not ip or self._arpnd_df.empty:
            return fhr_df

        rslt_df = self._arpnd_df.query(
            f'ipAddress=="{ip}" and not remote')

        if rslt_df.empty:
            return fhr_df

        # If we have more than one MAC addr, its hard to know which one
        uniq_mac = rslt_df['macaddr'].unique().tolist()
        if len(uniq_mac) != 1:
            return fhr_df

        macdf = self._macsobj.get(namespace=rslt_df.iloc[0].namespace,
                                  macaddr=uniq_mac[0], localOnly=True)
        if not macdf.empty:
            ign_ifs = ["bridge", "Vxlan1"]
            if device:
                macdf = macdf.query(
                    f'vlan != 0 and not oif.isin({ign_ifs}) and '
                    f' hostname != "{self._mlag_peers[device]}"')
            else:
                macdf = macdf.query(f'vlan != 0 and not oif.isin({ign_ifs})')

        for row in rslt_df.itertuples():
            mac_entry = macdf.query(f'hostname == "{row.hostname}"')
            if not mac_entry.empty:
                # for row in macdf.iterrows():
                idf = self._if_df.query(
                    f'hostname=="{row.hostname}" and '
                    f'ifname=="{mac_entry.oif.iloc[0]}"').copy()

                # We need to replace the VLAN in the if_df with what
                # is obtained from the MAC because of trunk ports.
                if idf.empty:
                    continue
                idf.at[idf.index, 'vlan'] = mac_entry.vlan.iloc[0]
                if (idf.master == 'bridge').all():
                    idf.at[idf.index, 'ipAddressList'] = f'{ip}/32'
                    # Assuming the VRF is identical across multiple entries
                    idf.at[idf.index, 'master'] = rslt_df.iloc[0].vrf
            else:
                idf = self._if_df.query(f'hostname=="{row.hostname}" and '
                                        f'ifname=="{row.oif}" and '
                                        f'type=="vlan"').copy()
                if idf.empty:
                    continue
            if fhr_df.empty:
                fhr_df = idf
            else:
                fhr_df = pd.concat([fhr_df, idf])
        return fhr_df

    def _get_if_vlan(self, device: str, ifname: str) -> int:
        oif_df = self._if_df[(self._if_df["hostname"] == device) &
                             (self._if_df["ifname"] == ifname)]

        if oif_df.empty:
            return []

        return oif_df.iloc[0]["vlan"]

    def _get_l2_nexthop(self, device: str, vrf: str, dest: str,
                        macaddr: str, protocol: str) -> list:
        """Get the bridged/tunnel nexthops
        We're passing protocol because we need to keep the return
        match the other get nexthop function returns. We don't really
        use protocol or determine it.
        """

        if self._arpnd_df.empty:
            return []

        rslt = self._arpnd_df[(self._arpnd_df['hostname'] == device) &
                              (self._arpnd_df['ipAddress'] == dest)]
        # the end of knowledge
        if rslt.empty:
            # Check if we have an EVPN entry as a route (symmetric routing)
            rslt = self._rdf.query(
                f'hostname == "{device}" and vrf == "{vrf}"')
            if not rslt.empty:
                # Check that we have a host route at this point
                ipvers = 6 if ':' in dest else 4
                if ((ipvers == 4 and rslt.iloc[0].prefix == f'{dest}/32') or
                        (ipvers == 6 and rslt.iloc[0].prefix == f'{dest}/128')):
                    overlay = rslt.iloc[0].nexthopIps[0]
                    return self._get_underlay_nexthop(device, [overlay],
                                                      ['default'], True)
            return []

        if rslt.empty:
            return []

        if not macaddr:
            macaddr = rslt.iloc[0]["macaddr"]
        oif = rslt.iloc[0]["oif"]
        # This is to handle the VRR interface on Cumulus Linux machines
        if oif.endswith("-v0"):
            oif = oif.split("-v0")[0]

        vlan = self._get_if_vlan(device, oif)

        if macaddr:
            mac_df = self._macsobj.get(namespace=rslt.iloc[0]['namespace'],
                                       hostname=device, macaddr=macaddr,
                                       vlan=[str(vlan)])

            if mac_df.empty:
                # On servers there's no bridge and thus no MAC table entry
                return [('', rslt.iloc[0].oif, False, protocol == "l2",
                         protocol, np.nan)]

            overlay = mac_df.iloc[0].remoteVtepIp or False
            if not overlay:
                return ([('', mac_df.iloc[0].oif, overlay, protocol == "l2",
                          protocol,
                          mac_df.iloc[0].timestamp)])
            else:
                # We assume the default VRF as the underlay. Can this change?
                return self._get_underlay_nexthop(device, [overlay],
                                                  ['default'], True)
        return []

    def _get_underlay_nexthop(self, hostname: str, vtep_list: list,
                              vrf_list: list, is_overlay: bool) -> pd.DataFrame:
        """Return the underlay nexthop given the Vtep and VRF"""

        # WARNING: This function is incomplete right now
        result = []

        if len(set(vrf_list)) != 1:
            # VTEP underlay can only be in a single VRF
            return result

        vrf = vrf_list[0].split(':')[-1]
        for vtep in vtep_list:
            if vtep not in self._underlay_dfs:
                self._underlay_dfs[vtep] = routes.RoutesObj(
                    context=self.ctxt).lpm(namespace=self.namespace,
                                           address=vtep, vrf=vrf)
            vtep_df = self._underlay_dfs[vtep]
            rslt = vtep_df.query(
                f'hostname == "{hostname}" and vrf == "{vrf}"')
            if not rslt.empty:
                if is_overlay:
                    intres = zip(rslt.nexthopIps.iloc[0].tolist(),
                                 rslt.oifs.iloc[0].tolist(),
                                 repeat(vtep), repeat(is_overlay),
                                 repeat(rslt.protocol.iloc[0]),
                                 repeat(rslt.timestamp.iloc[0])
                                 )
                elif rslt.protocol.iloc[0] == 'direct':
                    intres = zip([vtep], [rslt.oifs.iloc[0][0]], [False], [False],
                                 [rslt.protocol.iloc[0]], [rslt.timestamp.iloc[0]])

                else:
                    intres = zip(rslt.nexthopIps.iloc[0].tolist(),
                                 rslt.oifs.iloc[0].tolist(),
                                 repeat(False), repeat(is_overlay),
                                 repeat(rslt.protocol.iloc[0]),
                                 repeat(rslt.timestamp.iloc[0])
                                 )

                result.extend(list(intres))

        return result

    def _get_nexthops(self, device: str, vrf: str, dest: str, is_l2: bool,
                      vtep: str, macaddr: str) -> list:
        """Get nexthops (oif + IP + overlay) or just oif for given host/vrf.

        The overlay is a bit indicating we're getting into overlay or not.
        """

        if is_l2:
            if vtep:
                return self._get_underlay_nexthop(device, [vtep], [vrf], True)
            else:
                return self._get_l2_nexthop(device, vrf, dest, macaddr, 'l2')

        rslt = self._rdf.query(f'hostname == "{device}" and vrf == "{vrf}"')
        # The following condition is checking that we have a pure L3 nexthop or
        # the start of an underlay route. if its a pure L3 route, the nexthopIp
        # is not empty OR the protocol is not hmm--NXOS' host mobility
        # protocol--which also puts a final subnet route with EVPN also as an L3
        # route.
        if not rslt.empty and (len(rslt.nexthopIps.iloc[0]) != 0 and
                               rslt.nexthopIps.iloc[0][0] != '') and (
                                   rslt.protocol.iloc[0] != 'hmm'):
            # Handle overlay routes given how NXOS programs its FIB
            if rslt.oifs.explode().str.startswith('_nexthopVrf:').any():
                # We need to find the true NHIP
                return self._get_underlay_nexthop(
                    device,
                    rslt.nexthopIps.iloc[0].tolist(),
                    rslt.oifs.iloc[0].tolist(), True)
            elif not rslt.empty and (len(rslt.nexthopIps.iloc[0]) != 0 and
                                     rslt.nexthopIps.iloc[0][0] != '') and (
                                         not rslt.oifs.iloc[0].tolist()):
                # NXOS and recursive route handling
                return self._get_underlay_nexthop(
                    device, rslt.nexthopIps.iloc[0].tolist(), [vrf], False)
            return zip(rslt.nexthopIps.iloc[0].tolist(),
                       rslt.oifs.iloc[0].tolist(),
                       repeat(False), repeat(False),
                       repeat(rslt.protocol.iloc[0]),
                       repeat(rslt.timestamp.iloc[0]))

        # We've either reached the end of routing or the end of knowledge
        # Look for L2 nexthop
        if rslt.empty:
            protocol = ''
        else:
            protocol = rslt.protocol.iloc[0]
        return self._get_l2_nexthop(device, vrf, dest, None, protocol)

    @ lru_cache(maxsize=256)
    def _get_nh_with_peer(self, device: str, vrf: str, dest: str, is_l2: bool,
                          vtep_ip: str, macaddr: str) -> list:
        """Get the nexthops & peer node for each nexthop for a given device/vrf
        This uses the cached route lpm DF to get the nexthops. It
        also handles vlan subinterfaces, MLAG and plain bonds to get the
        valid nexthop peers.

        :param device: devicename to query in lpm DF for nexthop
        :type device: str

        :param vrf: VRF to qualify lpm DF for nexthop
        :type vrf: str

        :param dest: Destination IP we're searching forever, needed for arp/nd
        :type dest: str

        :param is_l2: If this is an L2 lookup
        :type is_l2: bool

        :param vtep_ip: VTEP IP address, can be empty string if not in underlay
        :type vtep_ip: str

        :param macaddr: Look for this MAC addr, not dest, as this is L2hop
        :type macaddr: str

        :rtype: list
        :return:
        list of tuples where each tuple is (oif, peerdevice, peerif, overlay)
        """

        nexthops = []

        # TODO: Can we have ECMP nexthops, one with NH IP and one without?
        nexthop_list = self._get_nexthops(
            device, vrf, dest, is_l2, vtep_ip, macaddr)
        new_nexthop_list = []
        # Convert each OIF into its actual physical list
        is_l2 = False
        for nhip, iface, overlay, is_l2, protocol, timestamp in nexthop_list:
            if macaddr and is_l2 and not overlay:
                new_nexthop_list.append((nhip, iface, overlay, is_l2,
                                         protocol, timestamp))
                continue

            if (not nhip or nhip == 'None') and iface:
                addr = dest
            else:
                addr = nhip
            if iface.endswith('-v0'):
                # Replace Cumulus' VRR entry with actual SVI
                iface = iface.split('-v0')[0]
            # This first pass is to handle Cumulus symmetric EVPN routes
            arpdf = self._arpnd_df.query(f'hostname=="{device}" and '
                                         f'ipAddress=="{addr}" and '
                                         f'oif=="{iface}"')
            if not arpdf.empty and arpdf.remote.all():
                macdf = self._macsobj.get(namespace=self.namespace,
                                          hostname=device,
                                          macaddr=arpdf.iloc[0].macaddr)
                if not macdf.empty and macdf.remoteVtepIp.all():
                    overlay = macdf.iloc[0].remoteVtepIp

                underlay_nh = self._get_underlay_nexthop(device, [overlay],
                                                         ['default'], True)
                new_nexthop_list.extend(underlay_nh)
            else:
                new_nexthop_list.append((nhip, iface, overlay, is_l2,
                                         protocol, timestamp))

        on_src_node = device in self.src_device
        for (nhip, iface, overlay, is_l2, protocol,
             timestamp) in new_nexthop_list:
            df = pd.DataFrame()
            errormsg = ''
            if is_l2 and macaddr and not overlay:
                if (not nhip or nhip == 'None') and iface:
                    addr = dest + '/'
                else:
                    addr = nhip + '/'
                df = self._if_df.query(
                    f'macaddr=="{macaddr}" '
                    f'and type != "bond_slave" '
                    f'and state != "down" '
                    f'and ipAddressList.str.startswith("{addr}")')
                if df.empty:
                    df = self._if_df.query(
                        f'ipAddressList.str.startswith("{addr}") and '
                        f'type !="bond_slave"')
                    if df.empty:
                        continue
            else:
                if not nhip:
                    nhip = dest
                arpdf = self._arpnd_df.query(f'hostname=="{device}" and '
                                             f'ipAddress=="{nhip}" and '
                                             f'oif=="{iface}"')
                if not arpdf.empty:
                    addr = nhip + '/'
                    df = self._if_df.query(
                        f'macaddr=="{arpdf.iloc[0].macaddr}" '
                        f'and type != "bond_slave" '
                        f'and state != "down" '
                        f'and ipAddressList.str.startswith("{addr}")')
                    if df.empty:
                        # In case of L2 interfaces as the nexthop, there'll be
                        # no IP address on the interface with matching NHIP.
                        df = self._if_df.query(
                            f'macaddr=="{arpdf.iloc[0].macaddr}" '
                            f'and type != "bond_slave"')
                elif protocol == 'direct':
                    continue
                nhip_df = self._if_df.query(
                    f'ipAddressList.str.startswith("{nhip}/") and '
                    f'type != "bond_slave" and hostname != "{device}"')
                if df.empty and not nhip_df.empty:
                    df = nhip_df
                elif on_src_node and not df.empty and not nhip_df.empty:
                    if ((df.hostname.unique().tolist() !=
                         nhip_df.hostname.unique().tolist()) and
                        (df.macaddr.unique().tolist() !=
                         nhip_df.macaddr.unique().tolist())):
                        errormsg = 'Possible anycast IP without anycast MAC'
                        is_l2 = True

                if df.empty:
                    continue

            # In case of centralized EVPN, its possible to find the NHIP on
            # unconnected devices if this is still the source device i.e.
            # server. If so, find FHR to get the real connected dev
            if device in self.src_device:
                check_fhr = self.source
            elif is_l2 and (df.iloc[0].hostname in self.dest_device):
                check_fhr = self.dest
            else:
                check_fhr = None

            if check_fhr:
                fhr_df = self._find_fhr_df(device, check_fhr)
                if not fhr_df.empty:
                    fhr_hosts = set(fhr_df['hostname'].tolist())

                    if check_fhr != self.dest and device not in fhr_hosts:
                        # Avoid looping everytime we hit the dest device
                        # We only need to do it once
                        df = df.query(f'hostname.isin({list(fhr_hosts)})')
                        if df.empty:
                            # The L3 nexthop is not the next L2 hop
                            df = fhr_df
                            is_l2 = True
                            # But what we're going to be forwarding on when
                            # we hit the next L2 hop is the MAC addr from the
                            # ARP entry, and so set the macaddr to that for now
                            if not arpdf.empty:
                                macaddr = arpdf.macaddr.unique().tolist()[0]
                        else:
                            # Fix the incoming interface
                            df = df.merge(fhr_df[['namespace', 'hostname',
                                                  'ifname']],
                                          on=['namespace', 'hostname'],
                                          how='outer') \
                                .fillna(method='ffill') \
                                .drop(columns=['ifname_x']) \
                                .rename(columns={'ifname_y': 'ifname'})

            # In case of some NOS such as NXOS with OSPF unnumbered, multiple
            # interfaces from the same device have the same IP and MAC. This
            # needs to be filtered to the precise interface. We do this by
            # matching the IP/MAC of this device's OIF with the ARP/ND table
            # on the nexthop device
            if (df.hostname.nunique() == 1) and (df.ifname.nunique() > 1):
                oif_df = self._if_df.query(f'hostname=="{device}" and '
                                           f' ifname=="{iface}"')
                if not oif_df.empty and oif_df.ipAddressList.iloc[0]:
                    revip = oif_df.ipAddressList.iloc[0].split('/')[0]
                    revvrf = "default" if overlay else vrf
                    revarp_df = self._arpnd_df.query(
                        f'hostname=="{df.hostname.unique()[0]}" and '
                        f'ipAddress=="{revip}" and vrf=="{revvrf}" and '
                        'state!="failed"')
                    if not revarp_df.empty:
                        df = df.query(f'ifname == "{revarp_df.oif.iloc[0]}"')
            df.apply(lambda x, nexthops:
                     nexthops.append((iface, x['hostname'],
                                      x['ifname'],  overlay,
                                      is_l2, nhip,
                                      macaddr or x.macaddr, protocol, errormsg,
                                      timestamp))
                     if (x['namespace'] in self.namespace) else None,
                     args=(nexthops,), axis=1)

        if not nexthops and is_l2:
            return [(None, None, None, False, is_l2, None, None, "l2", "",
                     np.nan)]

        return sorted(nexthops, key=lambda x: x[1])

    def get(self, **kwargs) -> pd.DataFrame:
        """return a pandas dataframe with the paths between src and dest
        :param kwargs:
        :return:
        :rtype: pd.DataFrame
        """

        if not self.ctxt.engine:
            raise AttributeError(
                "Specify an analysis engine using set engine " "command"
            )

        namespaces = kwargs.get("namespace", self.ctxt.namespace)
        if not namespaces:
            raise AttributeError("Must specify namespace to run the trace in")

        self.namespace = namespaces[0]
        src = kwargs.get("source", None)
        dest = kwargs.get("dest", None)
        dvrf = kwargs.get("vrf", "")

        if not src or not dest:
            raise AttributeError("Must specify trace source and dest")

        srcvers = ip_network(src, strict=False)._version
        dstvers = ip_network(dest, strict=False)._version
        if srcvers != dstvers:
            raise AttributeError(
                "Source and Dest MUST belong to same address familt")
        # All exceptions in the initial data gathering will happen in this init
        # After this, at least we know we have the data to work on
        self._init_dfs(self.namespace, src, dest)

        devices_iifs = OrderedDict()
        src_mtu = None
        for i in range(len(self._src_df)):
            item = self._src_df.iloc[i]
            devices_iifs[f'{item.hostname}/'] = {
                "iif": item["ifname"],
                "mtu": item["mtu"],
                "outMtu": item["mtu"],
                "overlay": '',
                "protocol": '',
                "error": [],
                "lookup": dest,
                "macaddr": None,
                "vrf": item['master'],
                'mtuMatch': True,  # Its the first node
                "is_l2": self.is_l2,
                "nhip": '',
                "overlay_nhip": '',
                "oif": item["ifname"],
                "timestamp": item["timestamp"],
                "l3_visited_devices": set(),
                "l2_visited_devices": set()
            }
            if src_mtu is None or (item.get('mtu', 0) < src_mtu):
                src_mtu = item.get('mtu', 0)
        if not dvrf:
            dvrf = item['master']
        if not dvrf:
            dvrf = "default"

        dest_device_iifs = OrderedDict()
        for i in range(len(self._dest_df)):
            item = self._dest_df.iloc[i]
            error = []
            dest_device_iifs[f'{item.hostname}/'] = {
                "iif": '',
                "vrf": item["master"] or "default",
                "mtu": item["mtu"],
                "outMtu": item["mtu"],
                "macaddr": None,
                "error": error,
                "overlay": '',
                "is_l2": False,
                "overlay_nhip": '',
                "oif": item["ifname"],
                "protocol": '',
                "lookup": '',
                "timestamp": item["timestamp"],
            }

        final_paths = []
        paths = []
        on_src_node = True

        # The logic is to loop through the nexthops till you reach the dest
        # device The topmost while is this looping. The next loop within handles
        # one nexthop at a time.The paths are constructed as a list of lists,
        # where each element of the outermost loop is one complete path and
        # each inner list represents one hop in that path. Each hop is the
        # list of devicename and incoming interface. loops are detected by
        # ensuring that no device is visited twice in the same VRF. The VRF
        # qualification is required to ensure packets coming back from a
        # firewall or load balancer are not tagged as duplicates.
        while devices_iifs:
            nextdevices_iifs = OrderedDict()
            newpaths = []
            revdf_check = True

            for devkey in devices_iifs:
                device = devkey.split('/')[0]
                iif = devices_iifs[devkey]["iif"]
                devvrf = devices_iifs[devkey]["vrf"]
                ioverlay = devices_iifs[devkey]["overlay"]
                macaddr = devices_iifs[devkey]['macaddr']
                l3_visited_devices = devices_iifs[devkey]['l3_visited_devices']
                l2_visited_devices = devices_iifs[devkey]['l2_visited_devices']
                is_l2 = devices_iifs[devkey]['is_l2']

                # We've reached the destination, so stop this loop
                destdevkey = f'{device}/'
                if destdevkey in dest_device_iifs:
                    if revdf_check:
                        vrfchk = dest_device_iifs[destdevkey]["vrf"]
                        rev_df = self._rpf_df.query(
                            f'hostname == "{device}" and vrf == "{vrfchk}"')
                        if rev_df.empty:
                            dest_device_iifs[destdevkey]['error'] \
                                .append('no reverse path')
                        revdf_check = False
                    pdev1 = devkey.split('/')[1]
                    for x in paths:
                        pdev2 = list(x[-1].keys())[0].split('/')[0]
                        if pdev1 != pdev2:
                            continue
                        copy_dest = copy(dest_device_iifs[destdevkey])
                        copy_dest['oif'] = devices_iifs[devkey]['oif']
                        copy_dest['iif'] = iif
                        copy_dest['mtu'] = devices_iifs[devkey]['mtu']
                        if copy_dest.get('mtu', 0) != src_mtu:
                            if 'Dst MTU != Src MTU' not in copy_dest['error']:
                                copy_dest['error'].append('Dst MTU != Src MTU')
                        # This is weird because we have no room to store the
                        # prev hop's outgoing IIF MTU on the last hop
                        copy_dest['outMtu'] = \
                            f'{devices_iifs[devkey]["outMtu"]}/' \
                            f'{dest_device_iifs[destdevkey]["outMtu"]}'
                        copy_dest['is_l2'] = is_l2
                        if not is_l2:
                            copy_dest['nhip'] = dest
                        copy_dest['mtuMatch'] = devices_iifs[devkey]['mtuMatch']
                        z = x + [OrderedDict(
                            {destdevkey: copy_dest})]
                        if z not in final_paths:
                            final_paths.append(z)
                    continue

                newdevices_iifs = {}  # NHs from this NH to add to the next round
                end_overlay = True
                if is_l2 or ioverlay:
                    if ioverlay:
                        ndst = ioverlay
                    else:
                        ndst = devices_iifs[devkey].get('nhip', None)
                    # Check if this is the end of the L2 path or overlay
                    nhdf = self._if_df.query(f'hostname=="{device}"')
                    if not nhdf.empty:
                        if srcvers == 4:
                            nhdf = nhdf.query(
                                f'ipAddressList.str.contains("{ndst}")')
                        else:
                            nhdf = nhdf.query(
                                f'ip6AddressList.str.contains("{ndst}")')
                    if not nhdf.empty:
                        ifmac = nhdf.macaddr.unique().tolist()
                        if (not macaddr) or (macaddr in ifmac):
                            ndst = dest
                            is_l2 = self.is_l2
                            ioverlay = ''
                            l2_visited_devices = set()
                    elif ioverlay:
                        end_overlay = False
                else:
                    ndst = dest
                if not ndst:
                    ndst = dest

                if not end_overlay:
                    ivrf = 'default'
                elif end_overlay and devices_iifs[devkey]['overlay_nhip']:
                    ivrf = self._get_vrf(device, '',
                                         devices_iifs[devkey]['overlay_nhip'])
                    if not ivrf:
                        ivrf = devvrf
                elif (not devices_iifs[devkey]['nhip'] or
                      (devices_iifs[devkey]['nhip'] == "169.254.0.1")):
                    ivrf = self._get_vrf(device, iif, '')
                else:
                    ivrf = self._get_vrf(device, '',
                                         devices_iifs[devkey]['nhip'])
                    if not ivrf:
                        ivrf = self._get_vrf(device, iif, '')

                if not ivrf:
                    ivrf = dvrf

                skey = device + ivrf
                if is_l2:
                    if skey in l2_visited_devices:
                        # This is a loop
                        if ioverlay:
                            devices_iifs[devkey]['error'] \
                                .append("Loop in underlay")
                        else:
                            devices_iifs[devkey]['error'] \
                                .append("L2 Loop detected")
                        for x in paths:
                            z = x + [OrderedDict({devkey:
                                                  devices_iifs[devkey]})]
                            if z not in final_paths:
                                final_paths.append(z)
                        continue
                    else:
                        l2_visited_devices.add(skey)
                else:
                    if skey in l3_visited_devices:
                        devices_iifs[devkey]['error'].append("L3 loop")
                        for x in paths:
                            z = x + [OrderedDict({devkey:
                                                  devices_iifs[devkey]})]
                            if z not in final_paths:
                                final_paths.append(z)
                        continue
                    else:
                        l3_visited_devices.add(skey)

                devices_iifs[devkey]['vrf'] = ivrf
                rt_ts = None
                if not (is_l2 or ioverlay):
                    rslt = self._rdf.query('hostname == "{}" and vrf == "{}"'
                                           .format(device, ivrf))
                    if not rslt.empty:
                        devices_iifs[devkey]['timestamp'] = rslt.timestamp.iloc[0]
                        devices_iifs[devkey]['protocol'] = rslt.protocol.iloc[0]
                        devices_iifs[devkey]['lookup'] = rslt.prefix.iloc[0]

                        rev_df = self._rpf_df.query(
                            f'hostname == "{device}" and vrf == "{ivrf}"')
                        if rev_df.empty and not on_src_node:
                            devices_iifs[devkey]['error'] \
                                .append('no reverse path')
                    else:
                        devices_iifs[devkey]['lookup'] = ''

                elif macaddr:
                    devices_iifs[devkey]['lookup'] = ''
                else:
                    devices_iifs[devkey]['lookup'] = ndst

                for i, nexthop in enumerate(self._get_nh_with_peer(
                        device, ivrf, ndst, is_l2, ioverlay, macaddr)):
                    error = []
                    (iface, peer_device, peer_if, overlay, is_l2,
                     nhip, macaddr, protocol, errmsg, timestamp) = nexthop
                    if not devices_iifs[devkey].get('protocol', ''):
                        devices_iifs[devkey]['protocol'] = protocol
                    if not rt_ts:
                        devices_iifs[devkey]['timestamp'] = timestamp
                    if errmsg and errmsg not in devices_iifs[devkey]['error']:
                        devices_iifs[devkey]['error'].append(errmsg)

                    if iface is not None:
                        if iface.startswith('vPC Peer'):
                            iface = self._mlag_peerlink[device]
                        elif iface.startswith('sup-eth1'):
                            iface = 'loopback0'
                        if peer_if.startswith('vPC Peer'):
                            peer_if = self._mlag_peerlink[peer_device]
                        elif peer_if.startswith('sup-eth1'):
                            peer_if = 'loopback0'
                        in_mtu = self._if_df[
                            (self._if_df["hostname"] == peer_device) &
                            (self._if_df["ifname"] == peer_if)
                        ].iloc[-1].mtu
                        out_mtu = self._if_df[
                            (self._if_df["hostname"] == device) &
                            (self._if_df["ifname"] == iface)
                        ].iloc[-1].mtu
                        if on_src_node and src_mtu > MAX_MTU:
                            src_mtu = out_mtu
                        mtu_match = in_mtu == out_mtu
                        if (in_mtu < src_mtu) or (out_mtu < src_mtu):
                            error.append('Hop MTU < Src Mtu')
                        if not end_overlay:
                            overlay = ioverlay
                            vrf = devvrf
                        else:
                            vrf = ivrf
                        if not nhip:
                            nhip = ndst
                        if overlay and not ioverlay:
                            overlay_nhip = ndst
                        elif not end_overlay:
                            overlay_nhip = devices_iifs[devkey]['overlay_nhip']
                        else:
                            overlay_nhip = ''
                        if overlay or not is_l2:
                            # We don't need to track MACaddr if its not a pure
                            # (non-overlay) L2 hop
                            macaddr = None

                        newdevices_iifs[f'{peer_device}/{device}'] = {
                            "iif": peer_if,
                            "vrf": vrf,
                            "macaddr": macaddr,
                            "overlay": overlay,
                            "mtu": in_mtu,
                            "outMtu": out_mtu,  # prev hop's outMTU, fixed ltr
                            "mtuMatch": mtu_match,
                            "is_l2": is_l2,
                            "nhip": nhip,
                            "oif": iface,
                            "error": error,
                            "overlay_nhip": overlay_nhip,
                            'l3_visited_devices': l3_visited_devices.copy(),
                            'l2_visited_devices': l2_visited_devices.copy()
                        }

                if not paths:
                    newpaths.append(
                        [OrderedDict({devkey: devices_iifs[devkey]})])

                # matching to attach the hop to the appropriate path
                pdev1 = devkey.split('/')[1]
                for x in paths:
                    xkey = list(x[-1].keys())[0]
                    pdev2 = xkey.split('/')[0]
                    if pdev1 != pdev2:
                        continue
                    z = x + [OrderedDict({devkey: devices_iifs[devkey]})]
                    if z not in newpaths:
                        newpaths.append(z)

                for x in newdevices_iifs:
                    if x not in nextdevices_iifs:
                        nextdevices_iifs[x] = newdevices_iifs[x]

            if newpaths:
                paths = newpaths

            devices_iifs = nextdevices_iifs
            on_src_node = False

        if not final_paths:
            # This occurs when a path traversal terminates due to an error such
            # as loop detected
            final_paths = paths
        return self._path_cons_result(final_paths)

    def _path_cons_result(self, paths):
        df_plist = []
        prev_hop = hop = None
        for i, path in enumerate(paths):
            if prev_hop:
                # Taking advantage of python's shallow copy, that this
                # also changes what's in df_plist
                prev_hop['oif'] = self._dest_df.iloc[0]['ifname']
                if isinstance(prev_hop['outMtu'], str) and '/' in prev_hop['outMtu']:
                    prev_hop['outMtu'] = int(prev_hop['outMtu'].split('/')[1])
                prev_hop['isL2'] = False
                prev_hop['nexthopIp'] = ''
                prev_hop['vtepLookup'] = ''
                prev_hop = None
            for j, ele in enumerate(path):
                item = list(ele)[0]
                if ele[item]['overlay']:
                    overlay = True
                else:
                    overlay = False
                lookup = ele[item].get("lookup", "")

                hop = {
                    "pathid": i + 1,
                    "hopCount": j,
                    "namespace": self.namespace,
                    "hostname": item.split('/')[0],
                    "iif": ele[item]["iif"],
                    "oif": ele[item]['oif'],
                    "vrf": ele[item]["vrf"],
                    "isL2": ele[item].get("is_l2", False),
                    "overlay": overlay,
                    "mtuMatch": ele[item].get("mtuMatch", np.nan),
                    "inMtu": ele[item].get("mtu", 0),
                    "outMtu": ele[item].get("outMtu", 0),
                    "protocol": ele[item].get('protocol', ''),
                    "ipLookup": lookup,
                    "vtepLookup": "",
                    "macLookup": "",
                    "nexthopIp": ele[item].get('nhip', ''),
                    "error": ', '.join(ele[item].get('error', [])),
                    "timestamp": ele[item].get("timestamp", np.nan)
                }
                df_plist.append(hop)
                # Update some of the edge info in the prev rowerr
                # Some path specific info cannot be populated in a hop
                # because of the algorithm. So, we save the info associated
                # with each hop of the path in the nexthop and have to do
                # this logic to populate the prev hop
                if prev_hop:
                    # Taking advantage of python's shallow copy, that this
                    # also changes what's in df_plist
                    prev_hop['nexthopIp'] = hop['nexthopIp']
                    if overlay:
                        prev_hop['vtepLookup'] = ele[item]["overlay"]
                    elif hop["isL2"]:
                        prev_hop["macLookup"] = ele[item]["macaddr"]
                    prev_hop['isL2'] = hop['isL2']
                    prev_hop['oif'] = hop['oif']
                    if isinstance(hop['outMtu'], str) and '/' in hop['outMtu']:
                        prev_hop['outMtu'] = int(hop['outMtu'].split('/')[0])
                    else:
                        prev_hop['outMtu'] = hop['outMtu']
                prev_hop = hop
        if prev_hop:
            # Taking advantage of python's shallow copy, that this
            # also changes what's in df_plist
            prev_hop['oif'] = self._dest_df.iloc[0]['ifname']
            if isinstance(prev_hop['outMtu'], str) and '/' in prev_hop['outMtu']:
                prev_hop['outMtu'] = int(prev_hop['outMtu'].split('/')[1])
            prev_hop['isL2'] = False
            prev_hop['nexthopIp'] = ''
            prev_hop['vtepLookup'] = ''
        paths_df = pd.DataFrame(df_plist)
        if not paths_df.empty and not any(paths_df.error):
            paths_df.drop(columns=['error'], inplace=True)
        return paths_df.drop_duplicates()

    def summarize(self, **kwargs):
        """return a pandas dataframe summarizing the path info between src/dest

        A copy of this function is in gui_path.py for reasons of efficiency
        :param kwargs:
        :return:
        :rtype: pd.DataFrame
        """

        path_df = self.get(**kwargs)

        if path_df.empty:
            return pd.DataFrame()

        namespace = self.namespace
        ns = {}
        ns[namespace] = {}

        perhopEcmp = path_df.query('hopCount != 0') \
                            .groupby(by=['hopCount'])['hostname']
        ns[namespace]['totalPaths'] = path_df['pathid'].max()
        ns[namespace]['perHopEcmp'] = perhopEcmp.nunique().tolist()
        ns[namespace]['maxPathLength'] = path_df.groupby(by=['pathid'])[
            'hopCount'].max().max()
        ns[namespace]['avgPathLength'] = path_df.groupby(by=['pathid'])[
            'hopCount'].max().mean()
        ns[namespace]['uniqueDevices'] = path_df['hostname'].nunique()
        ns[namespace]['mtuMismatch'] = not all(path_df['mtuMatch'])
        ns[namespace]['usesOverlay'] = any(path_df['overlay'])
        ns[namespace]['pathMtu'] = min(path_df.query('iif != "lo"')['inMtu'].min(),
                                       path_df.query('iif != "lo"')['outMtu'].min())

        summary_fields = ['totalPaths', 'perHopEcmp', 'maxPathLength',
                          'avgPathLength', 'uniqueDevices', 'pathMtu',
                          'usesOverlay', 'mtuMismatch']
        return pd.DataFrame(ns).reindex(summary_fields, axis=0) \
                               .convert_dtypes()
