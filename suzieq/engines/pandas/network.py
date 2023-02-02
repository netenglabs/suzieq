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
        fields = self.schema.get_display_fields(['default'])

        if ((self.iobj.start_time and self.iobj.end_time) or
                (self.iobj.view == 'all')):
            fields.insert(0, 'active')
            fields.append('timestamp')
        dflist = []
        if isinstance(addrlist, str):
            addrlist = [addrlist]
        for addr in addrlist:
            df = self._find_address(addr, **kwargs)
            if not df.empty:
                dflist.append(df)
        if dflist:
            df = pd.concat(dflist)

        if df.empty:
            return df

        if not df.empty and query_str:
            return df.query(query_str)

        return df[fields]

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

        if ((self.iobj.start_time and self.iobj.end_time) or
                (self.iobj.view == 'all')):
            cols.insert(0, 'active')
            cols.append('timestamp')
        # Convert Cisco-style MAC address to standard MAC addr format,
        # and lowercase all letters of the alphabet
        addr = convert_macaddr_format_to_colon(addr)

        addr_df = self._find_addr_arp(addr, **kwargs)
        if addr_df.empty:
            # Is this a locally attached interface IP to a device we're polling
            df = self._get_table_sqobj('address') \
                .get(vrf=vrf, address=[addr],
                     columns=['namespace', 'hostname', 'ifname', 'vlan', 'vrf',
                              'ipAddress', 'macaddr', 'timestamp'],
                     **kwargs)
            if df.empty:
                return addr_df

            # Only pick the entry with the address specified
            df = df.explode('ipAddress')
            df['ipAddress'] = df.ipAddress.str.split('/').str[0]
            if any(x in addr for x in ['::', '.']):
                df = df.query(f'ipAddress == "{addr}"').reset_index(drop=True)
            else:
                # If we're querying by MAC Addr and an interface has no IP,
                # without fillna, the entries are dropped due to dropna below
                # Arista's interfaces return a 0.0.0.0 if the primary address
                # isn't set. Weed out these entries

                df = df.query(f'macaddr == "{addr}"') \
                       .fillna('') \
                       .query('ipAddress != "0.0.0.0"') \
                       .reset_index(drop=True)

            df['type'] = 'interface'
            df['l2miss'] = False
            addr_df = df

        addr_df = self._find_first_hop_attach(addr_df)
        if vlan and not addr_df.empty:
            addr_df = addr_df.query(f'vlan == {vlan}')
        if vrf and not addr_df.empty:
            addr_df = addr_df.query(f'vrf == "{vrf}"')

        if addr_df.empty:
            return addr_df

        # If routed interface and unnumbered interfaces are used, we need to
        # identify the primary interface
        addr_df = addr_df \
            .dropna() \
            .drop_duplicates() \
            .reset_index(drop=True)

        if addr_df.type.unique().tolist() == ['routed']:
            addr_df = self._add_primary_interface(addr_df, addr)

        return addr_df[cols]

    def _find_bond_members(self, namespace: str, hostname: str,
                           ifname: str, timestamp: str) -> List[str]:
        """This function returns the member ports of a bond interface
        Args:
            namespace (str): Namespace of the host
            hostname (str): Hostname of the host
            ifname (str): Interface name of the bond
            timestamp (str): time string, of str(timestamp) format

        Returns:
            mbr_list(List[str]): List of member ports or input ifname
        """

        # get list  of namespaces, hostnames and ifnames to get info for

        ifdf = self._get_table_sqobj('interfaces',
                                     start_time='',
                                     end_time=timestamp) \
            .get(namespace=[namespace], hostname=[hostname], master=[ifname])

        if not ifdf.empty:
            return ifdf.ifname.unique().tolist()

        return [ifname]

    # pylint: disable=too-many-statements
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

        # This var tracks the set of hosts that were active and had
        # local ARP entries when last seen. Its used when view=all or
        # start and end times are specified.
        active_local_hosts = set()
        result = []
        if arpdf.empty:
            return pd.DataFrame(result)

        # When providing view=all or a start-time/end-time, since we're
        # using data from multiple table to produce the final output, we
        # need to know how to handle the time when we look for data in those
        # additional tables. For example, consider an ARP entry exists at time
        # t1, and then has changes at t2 and t3. Now lets say the user wants
        # to see all changes or changes between t1 and t3. WHen processing
        # the entries for row t1, We need to ensure that we look for data in
        # other tables only before t2, only before t3 when processing the
        # entry at time t2 and so on. We're figuring out the time window
        # with the code below.
        if not arpdf.empty:
            key_cols = ['namespace', 'hostname', 'ipAddress']
            arpdf = arpdf.sort_values(by=key_cols + ['timestamp'])
            arpdf['next_ts'] = arpdf.groupby(by=key_cols)['timestamp'] \
                                    .shift(-1)

        namespaces = arpdf.namespace.unique().tolist()
        hostnames = arpdf.hostname.unique().tolist()
        # Weed out MACVLAN interfaces on Cumulus that are for VIPs
        ifaces = [x for x in arpdf.oif.unique().tolist()
                  if not x.endswith('-v0')]
        macaddrs = arpdf.macaddr.unique().tolist()

        ifdf = self._get_table_sqobj('interfaces', start_time='') \
            .get(namespace=namespaces, hostname=hostnames,
                 ifname=ifaces)
        # We don't explicitly look for only local-only entries because
        # that precludes us addresses that were not remote in the past.
        macdf = self._get_table_sqobj('macs', start_time='') \
                    .get(namespace=namespaces, hostname=hostnames,
                         macaddr=macaddrs,
                         columns=['namespace', 'hostname', 'vlan', 'macaddr',
                                  'oif', 'remoteVtepIp', 'flags', 'active',
                                  'timestamp'])

        for arp_row in arpdf.itertuples():
            # We ignore the start time because the entries such as interface
            # may not have changeed in a very long time. Using the
            # start-time if one is provided can make us not return the
            # relevant data in situations where say, the interface has been
            # stable long before.
            # the start time.
            row_end_time = arp_row.next_ts or self.iobj.end_time
            tmpres = {}

            if getattr(arp_row, 'error', None):
                continue
            # Remote ARP entries are not what we need to track down locally
            # attached addresses. The if removes any always remote entries
            # from being considered.
            if (arp_row.remote and
                    arp_row.hostname not in active_local_hosts):
                continue

            if arp_row.oif.endswith('-v0'):
                # Ignore VRR interfaces in Cumulus, we got them via the
                # normal interface entry (without -v0)
                continue
            oif = arp_row.oif

            active = getattr(arp_row, 'active', True)
            # If an entry goes from local to being deleted, remove it
            if not active and arp_row.hostname in active_local_hosts:
                active_local_hosts.remove(arp_row.hostname)

            if active and not arp_row.remote:
                active_local_hosts.add(arp_row.hostname)

            row_ifdf = ifdf.query(f'namespace=="{arp_row.namespace}" and '
                                  f'hostname=="{arp_row.hostname}" and '
                                  f'ifname=="{arp_row.oif}"')
            # We need to select the entries that are closest to this
            # arpdf entry's timestamp
            if (not row_ifdf.empty and
                (self.iobj.end_time or self.iobj.view == "all") and
                    row_end_time is not pd.NaT):
                row_ifdf = row_ifdf[row_ifdf['timestamp'] <= row_end_time]

            if not row_ifdf.empty:
                netaddr = ip_address(arp_row.ipAddress)
                row_vrf = row_ifdf.master.unique().tolist()[0] or 'default'
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
                    tmpres.update({
                        'active': active,
                        'namespace': arp_row.namespace,
                        'hostname': arp_row.hostname,
                        'vrf': row_vrf,
                        'ipAddress': arp_row.ipAddress,
                        'vlan': row_ifdf.vlan.unique().tolist()[0],
                        'macaddr': arp_row.macaddr,
                        'ifname': oif,
                        'type': 'routed',
                        'l2miss': False,
                        'timestamp': arp_row.timestamp
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

                # If the entry switched from local to remote, mark it as
                # deleted
                if active and arp_row.remote:
                    # if the entry didnt switch from local to remote, we'd
                    # have continued above
                    # Routed interface
                    tmpres.update({
                        'active': False,
                        'namespace': arp_row.namespace,
                        'hostname': arp_row.hostname,
                        'vrf': row_vrf,
                        'ipAddress': arp_row.ipAddress,
                        'vlan': row_ifdf.vlan.unique().tolist()[0],
                        'macaddr': arp_row.macaddr,
                        'ifname': oif,
                        'type': 'bridged',
                        'l2miss': False,
                        'timestamp': arp_row.timestamp
                    })
                    result.append(tmpres)
                    active_local_hosts.remove(arp_row.hostname)
                    continue

                row_macdf = macdf.query(
                    f'namespace=="{arp_row.namespace}" and '
                    f'hostname=="{arp_row.hostname}" and '
                    f'macaddr=="{arp_row.macaddr}" and '
                    f'vlan=={ifdf.vlan.unique().tolist()}')
                # We need to select the entries that are closest to this
                # arpdf entry's timestamp. We can get duplicate entries
                # due to the various possibilities of mac table updates
                # (the mac table may not have changed in a long time or
                # it might've in the time window of this entry). We use
                # drop_duplicates later to remove duplicate entries.
                if (not row_macdf.empty and
                    (self.iobj.end_time or self.iobj.view == "all") and
                        row_end_time is not pd.NaT):
                    row_macdf = row_macdf[(row_macdf['timestamp']
                                           <= row_end_time) &
                                          (row_macdf['flags'] != "remote")]

                for mac_row in row_macdf.itertuples():
                    tmpres = {}
                    if (not mac_row.oif or mac_row.oif == "vPC Peer-Link" or
                            mac_row.flags == 'remote'):
                        continue
                    oifs = mac_row.oif

                    if not mac_row.active:
                        tmpres.update({
                            'active': active,
                            'namespace': arp_row.namespace,
                            'hostname': arp_row.hostname,
                            'vrf': row_vrf,
                            'ipAddress': arp_row.ipAddress,
                            'vlan': mac_row.vlan,
                            'macaddr': arp_row.macaddr,
                            'ifname': arp_row.oif,
                            'type': 'bridged',
                            'l2miss': True,
                            'timestamp': mac_row.timestamp
                        })
                    else:
                        tmpres.update({
                            'active': active,
                            'namespace': arp_row.namespace,
                            'hostname': arp_row.hostname,
                            'vrf': row_vrf,
                            'ipAddress': arp_row.ipAddress,
                            'vlan': mac_row.vlan,
                            'macaddr': arp_row.macaddr,
                            'ifname': oifs,
                            'type': 'bridged',
                            'l2miss': False,
                            'timestamp': arp_row.timestamp
                        })
                    result.append(tmpres)

                if row_macdf.empty:
                    for ele_vlan in row_ifdf.vlan.unique().tolist():
                        tmpres.update({
                            'active': active,
                            'namespace': arp_row.namespace,
                            'hostname': arp_row.hostname,
                            'vrf': row_vrf,
                            'ipAddress': arp_row.ipAddress,
                            'vlan': ele_vlan,
                            'macaddr': arp_row.macaddr,
                            'ifname':
                            ' '.join(row_ifdf.query(f'vlan == {ele_vlan}')
                                     .ifname.unique().tolist()),
                            'type': 'bridged',
                            'l2miss': True,
                            'timestamp': arp_row.timestamp
                        })
                    result.append(tmpres)

        return pd.DataFrame(result)

    # pylint: disable=too-many-statements
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

        # Calculate the next timestamp window for use with pulling in
        # correct info
        key_cols = ['namespace', 'hostname', 'vrf', 'ipAddress']
        l2_addr_df = l2_addr_df.sort_values(by=key_cols + ['timestamp'])
        l2_addr_df['next_ts'] = l2_addr_df.groupby(by=key_cols)['timestamp'] \
                                          .shift(-1)

        for row in l2_addr_df.itertuples():
            tmpres = {}

            active = getattr(row, 'active', True)
            match_ifname = row.ifname.split('.')[0]
            match_hostname = row.hostname
            match_namespace = row.namespace
            match_vrf = row.vrf
            # We ignore the start time because the entries such as interface
            # may not have changeed in a very long time. Using the
            # start-time if one is provided can make us not return the
            # relevant data in situations where say, the interface has been
            # stable long before.
            if self.iobj.end_time:
                if row.next_ts is pd.NaT:
                    match_endtime = self.iobj.end_time
                else:
                    match_endtime = str(row.next_ts)
            else:
                match_endtime = ''
            macobj = self._get_table_sqobj('macs', start_time='',
                                           end_time=match_endtime)
            lldpobj = self._get_table_sqobj('lldp', start_time='',
                                            end_time=match_endtime)

            while True:
                # Do not attempt to replace tmp_df with l2_addr_df and get
                # rid of do_contiue. For some weird reason, with pandas ver
                # 1.2.5, the explode line below hangs if we just use
                # l2_addr_df

                mbr_ports = self._find_bond_members(
                    match_namespace, match_hostname, match_ifname,
                    match_endtime)

                # If what we have is an address of an interface, don't chase
                # down the rabbit hole for first attach point
                if row.type == 'interface':
                    if match_ifname in mbr_ports:
                        mbr_ports = ''
                    match_ifname = row.ifname
                    break

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
                            match_endtime)
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

            tmpres.update({
                'active': active,
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

    def _add_primary_interface(self, addr_df: pd.DataFrame,
                               addr: str) -> pd.DataFrame:
        """Add the primary interface for this address if unnumbered

        Args:
            addr_df (pd.DataFrame): Dataframe with the address information
            addr (str): address to search for

        Returns:
            pd.DataFrame: Dataframe with primary interface rows added
        """

        hostnsgrp = addr_df.groupby(['hostname', 'namespace', 'vrf'])
        if len(hostnsgrp) > 1:
            # not a set of duplicated interfaces, return
            return addr_df

        # We need to add the empty string to handle junos devices which have
        # the IP address on .0 interfaces which the poller tended to classify
        # as subinterface.
        vrf = [addr_df.vrf[0], '']
        # We have a set of duplicated interfaces, find the primary
        df = self._get_table_sqobj('address', start_time='') \
            .get(namespace=[addr_df.namespace[0]],
                 hostname=[addr_df.hostname[0]],
                 vrf=vrf, type='loopback')

        if df.empty or ((df.ipAddressList.str.len() == 0).all() and
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
            .fillna('') \
            .reset_index(drop=True)

        if not df.empty:
            df['macaddr'] = "00:00:00:00:00:00"
            df['vlan'] = 0
            df['bondMembers'] = ''
            df['type'] = 'interface'
            df['l2miss'] = False
            if '::' in addr:
                df['ipAddress'] = df.ip6AddressList.apply(lambda x:
                                                          x.split('/')[0])
            else:
                df['ipAddress'] = df.ipAddressList.apply(lambda x:
                                                         x.split('/')[0])

            addr_df = addr_df.append(df[['namespace', 'hostname', 'ifname',
                                         'ipAddress', 'vrf', 'vlan', 'type',
                                        'l2miss', 'macaddr', 'bondMembers']])
        return addr_df
