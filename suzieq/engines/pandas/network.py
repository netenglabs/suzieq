from typing import List
from ipaddress import ip_address, ip_network

import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.shared.utils import convert_macaddr_format_to_colon


class NetworkObj(SqPandasEngine):
    '''Backend class to handle network queries'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'network'

    def find(self, **kwargs):
        '''Find the information requsted:

        address: given a MAC or IP address, find the first hop switch its
                 connected to
        '''

        addrlist = kwargs.pop('address', [])
        kwargs.pop('columns', ['default'])
        query_str = kwargs.pop('query_str', '')

        dflist = []
        if isinstance(addrlist, str):
            addrlist = [addrlist]
        for addr in addrlist:
            df = self._find_address(addr, **kwargs)
            if not df.empty:
                dflist.append(df)
        if dflist:
            df = pd.concat(dflist)

        if not df.empty and query_str:
            return df.query(query_str)

        return df

    def _find_asn(self, asn: List[str], **kwargs) -> pd.DataFrame:
        """Find the hosts with the ASN listed

        Args:
            asn (List[str]): List of ASNs, space separated

        Returns:
            pd.DataFrame: The dataframe with the info. The columns are-
                          namespace, hostname, asn
        """

        if not asn:
            return pd.DataFrame()

        _ = kwargs.pop('vlan', [])
        try:
            asn = [int(x) for x in asn]
        except ValueError:
            return pd.DataFrame({'error': ['ASNs must be an integers']})

        return self._get_table_sqobj('bgp') \
            .get(asn=asn, columns=['default'], **kwargs)

    def _find_address(self, addr: str, **kwargs) -> pd.DataFrame:
        """Find the origin or the first hop network device that owns this addr

        Args:
            addr (str): address to search for

        Returns:
            pd.DataFrame: Dataframe with the relevant information
        """

        vlan = kwargs.pop('vlan', '')
        vrf = kwargs.pop('vrf', '')
        columns = kwargs.get('columns', ['default'])
        cols = self.schema.get_display_fields(columns)

        if vlan:
            try:
                vlan = int(vlan)
            except ValueError:
                return pd.DataFrame({'error': ['vlan must be an integer']})

        # Convert Cisco-style MAC address to standard MAC addr format,
        # and lowercase all letters of the alphabet
        addr = convert_macaddr_format_to_colon(addr)

        addr_df = self._find_addr_arp(addr, **kwargs)
        if addr_df.empty:
            # Is this a locally attached interface IP to a device we're polling
            df = self._get_table_sqobj('address') \
                .get(vrf=vrf, address=[addr],
                     columns=['namespace', 'hostname', 'ifname', 'vlan', 'vrf',
                              'ipAddress', 'macaddr'],
                     **kwargs)
            if df.empty:
                return addr_df

            df['ipAddress'] = df.ipAddress.apply(
                lambda x: ', '.join([y.split('/')[0] for y in x]))

            df['bondMembers'] = ''
            df['type'] = 'interface'
            df['l2miss'] = False

            cols = [x for x in cols if x in df.columns]
            return df[cols]

        addr_df = self._find_first_hop_attach(addr_df)
        if vlan and not addr_df.empty:
            addr_df = addr_df.query(f'vlan == {vlan}')
        if vrf and not addr_df.empty:
            addr_df = addr_df.query(f'vrf == "{vrf}"')

        if addr_df.empty:
            return addr_df

        if addr_df.type.unique().tolist() == ['routed']:
            addr_df = self._find_primary_interface(addr_df, addr)

        # Drop duplicates that can occur as a consequence of resolving the
        # primary interface
        if not addr_df.empty:
            addr_df = addr_df \
                .dropna() \
                .drop_duplicates(subset=['namespace', 'hostname', 'vrf',
                                         'ipAddress', 'ifname', 'macaddr',
                                         'vlan']) \
                .reset_index(drop=True)

        return addr_df[cols]

    def _find_bond_members(self, namespace: str, hostname: str,
                           ifname: str, timestamp: int) -> List[str]:
        """This function returns the member ports of a bond interface
        Args:
            namespace (str): Namespace of the host
            hostname (str): Hostname of the host
            ifname (str): Interface name of the bond
            timestamp (int): Timestamp (epoch secs), at which to look for

        Returns:
            mbr_list(List[str]): List of member ports
        """

        # get list  of namespaces, hostnames and ifnames to get info for

        ifdf = self._get_table_sqobj('interfaces',
                                     start_time=str(timestamp-30),
                                     end_time=str(timestamp+30)) \
            .get(namespace=[namespace], hostname=[hostname], master=[ifname])

        if not ifdf.empty:
            return ifdf.ifname.unique().tolist()

        return [ifname]

    def _find_addr_arp(self, addr: str, **kwargs) -> pd.DataFrame:
        """Find the origin or the first hop network device that owns this addr

        Args:
            addr (str): address to search for

        Returns:
            pd.DataFrame: Dataframe with the relevant information
        """

        if any(x in addr for x in ['::', '.']):
            arpdf = self._get_table_sqobj('arpnd').get(
                ipAddress=addr.split(), **kwargs)
        else:
            arpdf = self._get_table_sqobj('arpnd').get(
                macaddr=addr.split(), **kwargs)

        result = []
        for row in arpdf.itertuples():
            tmpres = {}
            if getattr(row, 'error', None):
                continue
            if row.remote:
                # We're only looking for locally attached addresses
                continue
            if row.oif.endswith('-v0'):
                # Handle VRR interfaces in Cumulus
                oif = row.oif[:-3]
            else:
                oif = row.oif

            active = getattr(row, 'active', True)
            if not active:
                result.append({
                    'active': False,
                    'namespace': row.namespace,
                    'hostname': row.hostname,
                    'vrf': '-',
                    'ipAddress': row.ipAddress,
                    'vlan': '-',
                    'macaddr': row.macaddr,
                    'ifname': row.oif,
                    'type': 'bridged',
                    'l2miss': False,
                    'timestamp': row.timestamp
                })
                continue

            ifdf = self._get_table_sqobj('interfaces') \
                .get(namespace=[row.namespace], hostname=[row.hostname],
                     ifname=[oif])

            if not ifdf.empty:
                netaddr = ip_address(row.ipAddress)
                vrf = ifdf.master.unique().tolist()[0] or 'default'
                vlan_list = ifdf.vlan.astype(str).unique().tolist()
                try:
                    vlan = vlan_list[0]
                    vlan = int(vlan)
                except ValueError:
                    # ignore if the conversion of the vlan to integer has
                    # failed
                    pass
                # The code below checks if the provided address belongs to
                # the interface subnet. If it does, its a bridged address
                # else its a routed address i.e. you use routing to reach it.
                if not ifdf.ipAddressList.apply(
                        lambda subnets, netaddr:
                        False if not subnets.any() else
                        any(netaddr in ip_network(subnet, strict=False)
                            for subnet in subnets),
                        args=(netaddr,)).any():
                    # Routed interface
                    if hasattr(row, 'active'):
                        tmpres['active'] = True  # False case handled above

                    tmpres.update({
                        'namespace': row.namespace,
                        'hostname': row.hostname,
                        'vrf': vrf,
                        'ipAddress': row.ipAddress,
                        'vlan': vlan,
                        'macaddr': row.macaddr,
                        'ifname': oif,
                        'type': 'routed',
                        'l2miss': False,
                        'timestamp': row.timestamp
                    })
                    result.append(tmpres)
                    continue

                # At this point, we're dealing with bridged addresses, and as
                # an endpoint I'm expecting an SVI. Its possible its an
                # interface address on a routed link, but we cover that above
                # or via fetching the address table in the code that calls this
                # function.
                if 'vlan' not in ifdf.type.unique():
                    continue
                macdf = self._get_table_sqobj('macs') \
                    .get(namespace=[row.namespace], hostname=[row.hostname],
                         vlan=vlan_list,
                         macaddr=[row.macaddr],
                         columns=['default'],
                         local=True)
                if not macdf.empty:
                    oifs = [x for x in macdf.oif.unique() if x !=
                            "vPC Peer-Link"]
                    if not oifs:
                        continue
                    if hasattr(row, 'active'):
                        tmpres['active'] = True
                    tmpres.update({
                        'namespace': row.namespace,
                        'hostname': row.hostname,
                        'vrf': vrf,
                        'ipAddress': row.ipAddress,
                        'vlan': vlan,
                        'macaddr': row.macaddr,
                        'ifname': oifs[0],
                        'type': 'bridged',
                        'l2miss': False,
                        'timestamp': row.timestamp
                    })
                    result.append(tmpres)
                else:
                    if hasattr(row, 'active'):
                        tmpres['active'] = True

                    tmpres.update({
                        'namespace': row.namespace,
                        'hostname': row.hostname,
                        'vrf': vrf,
                        'ipAddress': row.ipAddress,
                        'vlan': vlan,
                        'macaddr': row.macaddr,
                        'ifname': ' '.join(ifdf.ifname.unique().tolist()),
                        'type': 'bridged',
                        'l2miss': True,
                        'timestamp': row.timestamp
                    })
                    result.append(tmpres)

        return pd.DataFrame(result)

    def _find_first_hop_attach(self, addr_df: pd.DataFrame) -> pd.DataFrame:
        """Find the first hop switch attachment point for this address

        Args:
            addr_df (pd.DataFrame): Dataframe with the address information

        Returns:
            pd.DataFrame: Dataframe with the L2 attachment point information
        """

        # We'll need to resolve bond interfaces first
        l2_addr_df = addr_df
        if l2_addr_df.empty:
            return addr_df

        result = []
        for row in l2_addr_df.itertuples():
            tmpres = {}

            active = getattr(row, 'active', True)
            if not active:
                result.append({
                    'active': False,
                    'namespace': row.namespace,
                    'hostname': row.hostname,
                    'vrf': row.vrf,
                    'ipAddress': row.ipAddress,
                    'vlan': row.vlan,
                    'macaddr': row.macaddr,
                    'ifname': row.ifname,
                    'bondMembers': '-',
                    'type': row.type,
                    'l2miss': row.l2miss,
                    'timestamp': row.timestamp
                })
                continue

            match_ifname = row.ifname.split('.')[0]
            match_hostname = row.hostname
            match_namespace = row.namespace
            match_vrf = row.vrf
            match_endtime = str(row.timestamp.timestamp() + 30)
            match_starttime = str(row.timestamp.timestamp() - 30)
            macobj = self._get_table_sqobj('macs', start_time=match_starttime,
                                           end_time=match_endtime)
            lldpobj = self._get_table_sqobj('lldp', start_time=match_starttime,
                                            end_time=match_endtime)

            while True:
                # Do not attempt to replace tmp_df with l2_addr_df and get
                # rid of do_contiue. For some weird reason, with pandas ver
                # 1.2.5, the explode line below hangs if we just use
                # l2_addr_df

                mbr_ports = self._find_bond_members(
                    match_namespace, match_hostname, match_ifname,
                    row.timestamp.timestamp())

                lldp_df = lldpobj.get(namespace=[row.namespace],
                                      hostname=[row.hostname],
                                      ifname=mbr_ports)

                if not lldp_df.empty:
                    peer_host = lldp_df.peerHostname.unique().tolist()[0]
                    if row.type == 'routed':
                        match_hostname = peer_host
                        match_ifname = lldp_df.peerIfname.unique().tolist()[0]
                        mbr_ports = self._find_bond_members(
                            match_namespace, match_hostname, match_ifname,
                            row.timestamp.timestamp())
                        # Need to get VRF for the interface
                        ifdf = self._get_table_sqobj('interfaces') \
                            .get(namespace=[match_namespace],
                                 hostname=[match_hostname],
                                 ifname=[match_ifname])
                        if not ifdf.empty:
                            match_vrf = ifdf.master.unique().tolist()[
                                0] or 'default'
                        # Routed ports never go more than one hop
                        break

                    macdf = macobj.get(namespace=[match_namespace],
                                       hostname=[peer_host],
                                       macaddr=row.macaddr,
                                       vlan=str(row.vlan),
                                       columns=['namespace', 'hostname',
                                                'vlan', 'macaddr', 'oif'])
                    if not macdf.empty:
                        match_hostname = peer_host
                        match_ifname = macdf.oif.unique().tolist()[0]
                    else:
                        break
                else:
                    break

            if match_ifname in mbr_ports:
                mbr_ports = ''

            if 'active' in addr_df.columns:
                tmpres['active'] = True  # False has been handled already

            tmpres.update({
                'namespace': row.namespace,
                'hostname': match_hostname,
                'vrf': match_vrf,
                'ipAddress': row.ipAddress,
                'vlan': row.vlan,
                'macaddr': row.macaddr,
                'ifname': match_ifname,
                'bondMembers': ', '.join(mbr_ports),
                'type': row.type,
                'l2miss': row.l2miss,
                'timestamp': row.timestamp
            })
            result.append(tmpres)

        if result:
            return pd.DataFrame(result)

        return addr_df

    def _find_primary_interface(self, addr_df: pd.DataFrame,
                                addr: str) -> pd.DataFrame:
        """Find the primary interface for this address

        Args:
            addr_df (pd.DataFrame): Dataframe with the address information
            addr (str): address to search for

        Returns:
            pd.DataFrame: Dataframe with primary interface rows only
        """

        hostnsgrp = addr_df.groupby(['hostname', 'namespace', 'vrf'])
        if len(hostnsgrp) > 1:
            # not a set of duplicated interfaces, return
            return addr_df

        # We have a set of duplicated interfaces, find the primary
        vrf = addr_df.vrf[0]
        if vrf == 'default':
            # Handle older records which have an empty string as default
            vrf = ['default', '']
        else:
            vrf = [vrf]
        df = self._get_table_sqobj('address') \
            .get(namespace=[addr_df.namespace[0]],
                 hostname=[addr_df.hostname[0]],
                 vrf=vrf, type='loopback')

        if df.empty:
            return addr_df

        if ((df.ipAddressList.str.len() == 0).all() and
                (df.ip6AddressList.str.len() == 0).all()):
            # Junos interfaces have IP address on the subinterface, and
            # so look for that.
            ifnames = [f'{x}.0' for x in df.ifname.unique()]
            df = self._get_table_sqobj('address') \
                     .get(namespace=[addr_df.namespace[0]],
                          hostname=[addr_df.hostname[0]],
                          vrf=vrf, ifname=ifnames)

        df = df.explode('ipAddressList').explode('ip6AddressList') \
            .query(f'ipAddressList.str.startswith("{addr}/") or '
                   f'ip6AddressList.str.startswith("{addr}/")') \
            .reset_index(drop=True)

        if df.empty:
            return addr_df

        for row in df.itertuples():
            addr_df = addr_df.append(
                {'namespace': row.namespace,
                 'hostname': row.hostname,
                 'ifname': row.ifname,
                 'vrf': row.vrf,
                 'ipAddress': row.ipAddressList.split('/')[0],
                 'vlan': 0,
                 'macaddr': row.macaddr,
                 'bondMembers': '',
                 'type': 'interface',
                 'l2miss': False,
                 'timestamp': row.timestamp},
                ignore_index=True)

        addr_df['type'] = 'interface'
        return addr_df
