from typing import List
import pandas as pd
from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.shared.utils import convert_macaddr_format_to_colon


class NetworkObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'network'

    def get(self, **kwargs):
        """Get the information requested"""

        kwargs.get('view', self.iobj.view)
        columns = kwargs.pop('columns', ['default'])
        kwargs.pop('addnl_fields', [])
        user_query = kwargs.pop('query_str', '')
        os = kwargs.pop('os', [])
        model = kwargs.pop('model', [])
        vendor = kwargs.pop('vendor', [])
        os_version = kwargs.pop('version', [])
        namespace = kwargs.pop('namespace', [])

        drop_cols = []
        show_cols = self.schema.get_display_fields(columns)
        if columns != '*' and 'sqvers' in show_cols:
            # Behavior in engineobj.py
            show_cols.remove('sqvers')

        if os or model or vendor or os_version:
            df = self._get_table_sqobj('device').get(
                columns=['namespace', 'hostname', 'os', 'model', 'vendor',
                         'version'],
                os=os,
                model=model,
                vendor=vendor,
                version=os_version,
                namespace=namespace,
                **kwargs)
        else:
            df = self._get_table_sqobj('device').get(
                columns=['namespace', 'hostname'], namespace=namespace,
                **kwargs)

        if df.empty:
            return pd.DataFrame()

        namespace = df.namespace.unique().tolist()
        hosts = df.hostname.unique().tolist()
        dev_nsgrp = df.groupby(['namespace'])

        # Get list of namespaces we're polling
        pollerdf = self._get_table_sqobj('sqPoller') \
            .get(columns=['namespace', 'hostname', 'service', 'status',
                          'timestamp'],
                 namespace=namespace, hostname=hosts)

        if pollerdf.empty:
            return pd.DataFrame()

        nsgrp = pollerdf.groupby(by=['namespace'])
        pollerns = sorted(pollerdf.namespace.unique().tolist())
        newdf = pd.DataFrame({
            'namespace': pollerns,
            'deviceCnt': dev_nsgrp['hostname'].nunique().tolist(),
            'serviceCnt': nsgrp['service'].nunique().tolist()
        })
        errsvc_df = pollerdf.query('status != 0 and status != 200') \
                            .groupby(by=['namespace'])['service'] \
                            .nunique().reset_index()
        newdf = newdf.merge(errsvc_df, on=['namespace'], how='left',
                            suffixes=['', '_y']) \
            .rename({'service': 'errSvcCnt'}, axis=1) \
            .fillna({'errSvcCnt': 0})
        newdf['errSvcCnt'] = newdf['errSvcCnt'].astype(int)

        # What protocols exist
        for table, fld in [('ospf', 'hasOspf'), ('bgp', 'hasBgp'),
                           ('evpnVni', 'hasVxlan'), ('mlag', 'hasMlag')]:
            df = self._get_table_sqobj(table) \
                .get(namespace=pollerns, hostname=hosts,
                     columns=['namespace'])
            if df.empty:
                newdf[fld] = False
                continue

            gotns = df.namespace.unique().tolist()
            newdf[fld] = newdf.apply(
                lambda x, y: True if x.namespace in y else False,
                axis=1, args=(gotns,))

        if 'sqvers' in show_cols:
            newdf['sqvers'] = self.schema.version
        newdf['active'] = True
        newdf = self._handle_user_query_str(newdf, user_query)

        # Look for the rest of info only in selected namepaces
        newdf['lastUpdate'] = nsgrp['timestamp'].max() \
            .reset_index()['timestamp']

        return newdf.drop(columns=drop_cols)[show_cols]

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

    def summarize(self, **kwargs):
        '''Summarize for network

        Summarize for network is a bit different from the rest of the
        summaries because its not grouped by namespace.
        '''

        df = self.get(**kwargs)

        if df.empty:
            return df

        self.ns = pd.DataFrame({
            'namespacesCnt': [df.namespace.count()],
            'servicePerNsStat': [[df.serviceCnt.min(), df.serviceCnt.max(),
                                  df.serviceCnt.median()]],
            'nsWithMlagCnt': [df.loc[df.hasMlag].shape[0]],
            'nsWithBgpCnt': [df.loc[df.hasBgp].shape[0]],
            'nsWithOspfCnt': [df.loc[df.hasOspf].shape[0]],
            'nsWithVxlanCnt': [df.loc[df.hasVxlan].shape[0]],
            'nsWithErrsvcCnt': [df.loc[df.errSvcCnt != 0].shape[0]],
        })

        # At this point we have a single row with index 0, so rename
        return self.ns.T.rename(columns={0: 'summary'})

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

        # Convert Cisco-style MAC address to standard MAC addr format,
        # and lowercase all letters of the alphabet
        if '.' in addr:
            addr = convert_macaddr_format_to_colon(addr)
        addr = addr.lower()

        addr_df = self._find_addr_arp(addr, **kwargs)
        if addr_df.empty:
            return addr_df
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
            .drop_duplicates(subset=['namespace', 'hostname', 'vrf']) \
            .reset_index(drop=True)

        if addr_df.type.unique().tolist() == ['routed']:
            addr_df = self._find_primary_interface(addr_df, addr)

        return addr_df

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
            if row.oif.endswith('-v0'):
                # Handle VRR interfaces in Cumulus
                oif = row.oif[:-3]
            else:
                oif = row.oif
            ifdf = self._get_table_sqobj(
                'interfaces',
                start_time=str(row.timestamp.timestamp()-30),
                end_time=str(row.timestamp.timestamp()+30)) \
                .get(namespace=[row.namespace], hostname=[row.hostname],
                     ifname=[oif])

            if not ifdf.empty:
                if 'vlan' not in ifdf.type.unique():
                    # Routed interface
                    result.append({
                        'namespace': row.namespace,
                        'hostname': row.hostname,
                        'vrf': ifdf.master.unique().tolist()[0] or 'default',
                        'ipAddress': row.ipAddress,
                        'vlan': ifdf.vlan.astype(str).unique().tolist()[0],
                        'macaddr': row.macaddr,
                        'ifname': oif,
                        'type': 'routed',
                        'timestamp': row.timestamp
                    })
                    continue

                macdf = self._get_table_sqobj(
                    'macs',
                    start_time=str(row.timestamp.timestamp()-30),
                    end_time=str(row.timestamp.timestamp()+30)) \
                    .get(namespace=[row.namespace], hostname=[row.hostname],
                         vlan=ifdf.vlan.astype(str).unique().tolist(),
                         macaddr=[row.macaddr],
                         columns=['default'],
                         localOnly=True)
                if not macdf.empty:
                    oifs = [x for x in macdf.oif.unique() if x !=
                            "vPC Peer-Link"]
                    if not oifs:
                        continue
                    result.append({
                        'namespace': row.namespace,
                        'hostname': row.hostname,
                        'vrf': ifdf.master.unique().tolist()[0] or 'default',
                        'ipAddress': row.ipAddress,
                        'vlan': ifdf.vlan.astype(str).unique().tolist()[0],
                        'macaddr': row.macaddr,
                        'ifname': oifs[0],
                        'type': 'bridged',
                        'timestamp': row.timestamp
                    })

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
            result.append({
                'namespace': row.namespace,
                'hostname': match_hostname,
                'vrf': match_vrf,
                'ipAddress': row.ipAddress,
                'vlan': row.vlan,
                'macaddr': row.macaddr,
                'ifname': match_ifname,
                'bondMembers': ', '.join(mbr_ports),
                'type': row.type,
                'timestamp': row.timestamp
            })

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
        df = self._get_table_sqobj('interfaces') \
            .get(namespace=[addr_df.namespace[0]],
                 hostname=[addr_df.hostname[0]],
                 vrf=[addr_df.vrf[0]], type='loopback')
        if df.empty:
            return addr_df

        df = df.explode('ipAddressList').explode('ip6AddressList') \
            .query(f'ipAddressList.str.startswith("{addr}/") or '
                   f'ip6AddressList.str.startswith("{addr}/")') \
            .reset_index(drop=True)

        if not df.empty:
            addr_df['ifname'] = df.ifname.unique().tolist()[0]
            if df.type[0] == "bond":
                addr_df['bondMbrs'] = self._find_bond_members(
                    addr_df.namespace[0], addr_df.hostname[0],
                    addr_df.ifname[0], addr_df.timestamp[0].timestamp())
            else:
                addr_df['bondMbrs'] = ''

            return addr_df

        return addr_df
