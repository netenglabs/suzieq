from typing import List
import pandas as pd
import numpy as np
from .engineobj import SqPandasEngine
from suzieq.sqobjects import get_sqobject
from suzieq.utils import convert_macaddr_format_to_colon


class NetworkObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'network'

    def get(self, **kwargs):
        """Get the information requested"""

        view = kwargs.get('view', self.iobj.view)
        columns = kwargs.pop('columns', ['default'])
        addnl_fields = kwargs.pop('addnl_fields', [])
        user_query = kwargs.pop('query_str', '')
        os = kwargs.pop('os', [])
        model = kwargs.pop('model', [])
        vendor = kwargs.pop('vendor', [])
        os_version = kwargs.pop('version', [])
        namespace = kwargs.pop('namespace', [])

        drop_cols = []

        if os or model or vendor or os_version:
            df = get_sqobject('device')(context=self.ctxt).get(
                columns=['namespace', 'hostname', 'os', 'model', 'vendor',
                         'version'],
                os=os,
                model=model,
                vendor=vendor,
                version=os_version,
                namespace=namespace,
                **kwargs)
        else:
            df = get_sqobject('device')(context=self.ctxt).get(
                columns=['namespace', 'hostname'], namespace=namespace,
                **kwargs)

        if df.empty:
            return pd.DataFrame()

        namespace = df.namespace.unique().tolist()

        # Get list of namespaces we're polling
        pollerdf = get_sqobject('sqPoller')(context=self.ctxt) \
            .get(columns=['namespace', 'hostname', 'service', 'status', 'timestamp'],
                 namespace=namespace,
                 **kwargs)
        if pollerdf.empty:
            return pd.DataFrame()

        nsgrp = pollerdf.groupby(by=['namespace'])
        pollerns = sorted(pollerdf.namespace.unique().tolist())
        newdf = pd.DataFrame({
            'namespace': pollerns,
            'deviceCnt': nsgrp['hostname'].nunique().tolist(),
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
            df = get_sqobject(table)(context=self.ctxt) \
                .get(namespace=pollerns, columns=['namespace'])
            if df.empty:
                newdf[fld] = False
                continue

            gotns = df.namespace.unique().tolist()
            newdf[fld] = newdf.apply(
                lambda x, y: True if x.namespace in y else False,
                axis=1, args=(gotns,))

        newdf = self._handle_user_query_str(newdf, user_query)

        # Look for the rest of info only in selected namepaces
        newdf['lastUpdate'] = nsgrp['timestamp'].max() \
            .reset_index()['timestamp']

        return newdf.drop(columns=drop_cols)

    def find(self, **kwargs):
        '''Find the information requsted:

        address: given a MAC or IP address, find its owner OR the first hop
                 device its connected to
        asn: given an ASN, find the list of BGP sessions associated with this ASN
        '''

        addrlist = kwargs.pop('address', [])
        asn = kwargs.pop('asn', '')
        columns = kwargs.pop('columns', ['default'])
        resolve_bond = kwargs.pop('resolve_bond', False)

        dflist = []
        if isinstance(addrlist, str):
            addrlist = [addrlist]
        for addr in addrlist:
            df = self._find_address(addr, resolve_bond, **kwargs)
            if not df.empty:
                dflist.append(df)
        if dflist:
            df = pd.concat(dflist)
        else:
            df = self._find_asn(asn, **kwargs)

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

        return get_sqobject('bgp')(context=self.ctxt).get(asn=asn, columns=['default'],
                                                          **kwargs)

    def _find_address(self, addr: str, resolve_bond: bool,
                      **kwargs) -> pd.DataFrame:
        """Find the origin or the first hop network device that owns this addr

        Args:
            addr (str): address to search for

        Returns:
            pd.DataFrame: Dataframe with the relevant information
        """

        cols = ['namespace', 'hostname', 'ifname',
                'vrf', 'ipAddress', 'vlan', 'macaddr', 'how', 'timestamp']

        vlan = kwargs.pop('vlan', '')
        vrf = kwargs.pop('vrf', '')

        # Convert Cisco-style MAC address to standard MAC addr format,
        # and lowercase all letters of the alphabet
        if '.' in addr:
            addr = convert_macaddr_format_to_colon(addr)
        addr = addr.lower()

        addr_df = get_sqobject('address')(context=self.ctxt).get(
            address=addr.split(),
            columns=['namespace', 'hostname', 'ifname', 'vrf', 'ipAddressList',
                     'ip6AddressList', 'macaddr', 'vlan', 'timestamp'],
            **kwargs)

        if addr_df.empty:
            addr_df = self._find_addr_arp(addr, **kwargs)
            addr_df['how'] = 'derived'
            do_continue = True
        else:
            do_continue = False
            addr_df['how'] = 'polled'
            addr_df = addr_df.explode('ipAddressList').fillna('')

        if not addr_df.empty:
            if do_continue:
                # Not polled entry, and so we need to follow L2 links
                addr_df = self._find_l2_attach(addr_df, **kwargs)
            if vlan:
                addr_df = addr_df.query(f'vlan == {vlan}')
            if vrf:
                addr_df = addr_df.query(f'vrf == "{vrf}"')
            if resolve_bond:
                addr_df = self._find_bond_slaves(addr_df
                                                 .reset_index(drop=True))
            return addr_df.rename(
                columns={'ipAddressList': 'ipAddress',
                         'ip6AddressList': 'ip6Address'}, errors='ignore')[cols] \
                .dropna()
        return addr_df

    def _find_bond_slaves(self, df: pd.DataFrame) -> pd.DataFrame:
        """This function splits out the bond ports if requested

        Assumes that the field ifname exists in the dataframe

        Args:
            df (pd.DataFrame): The dataframe with the field that needs
                               to be resolved

        Returns:
            pd.DataFrame: The dataframe with the bond name resolved if
                          possible, else unchanged
        """

        # get list  of namespaces, hostnames and ifnames to get info for
        ns = df.namespace.unique().tolist()
        hosts = df.hostname.unique().tolist()
        master = df.ifname.unique().tolist()

        ifdf = get_sqobject('interfaces')(context=self.ctxt) \
            .get(namespace=ns, hostname=hosts, master=master)

        if ifdf.empty:
            return df

        for i, row in enumerate(df.itertuples()):
            newiflist = ifdf.apply(
                lambda x, y: x.ifname
                if (x.master == row.ifname) and (x.namespace == row.namespace) and (x.hostname == row.hostname) else '',
                args=(row, ), axis=1).tolist()
            if newiflist:
                df.at[i, 'ifname'] = ', '.join(filter(None, newiflist))

        return df

    def _find_addr_arp(self, addr: str, **kwargs) -> pd.DataFrame:
        """Find the origin or the first hop network device that owns this addr

        Args:
            addr (str): address to search for

        Returns:
            pd.DataFrame: Dataframe with the relevant information
        """

        cols = ['namespace', 'hostname', 'ifname',
                'vrf', 'ipAddress', 'macaddr', 'timestamp']

        if any(x in addr for x in ['::', '.']):
            arpdf = get_sqobject('arpnd')(context=self.ctxt).get(
                ipAddress=addr, **kwargs)
        else:
            arpdf = get_sqobject('arpnd')(context=self.ctxt).get(
                macaddr=addr, **kwargs)

        if not arpdf.empty:
            ifdf = get_sqobject('interfaces')(context=self.ctxt) \
                .get(namespace=arpdf.namespace.unique().tolist(),
                     hostname=arpdf.hostname.unique().tolist(),
                     ifname=arpdf.oif.unique().tolist())

            arpdf = arpdf.merge(ifdf[['namespace', 'hostname', 'ifname', 'vlan',
                                      'master']],
                                left_on=['namespace', 'hostname', 'oif'],
                                right_on=['namespace',
                                          'hostname', 'ifname'],
                                how='left', suffixes=['', '_y']) \
                .drop(columns=['oif']) \
                .rename(columns={'master': 'vrf'})

            macdf = get_sqobject('macs')(context=self.ctxt) \
                .get(namespace=arpdf.namespace.unique().tolist(),
                     hostname=arpdf.hostname.unique().tolist(),
                     vlan=arpdf.vlan.astype(str).unique().tolist(),
                     macaddr=arpdf.macaddr.unique().tolist(),
                     columns=['default'],
                     localOnly=True)
            if not macdf.empty:
                arpdf = arpdf.merge(macdf,
                                    on=['namespace', 'hostname',
                                        'vlan', 'macaddr'],
                                    how='left', suffixes=['', '_y']) \
                    .drop(columns=['remoteVtepIp', 'ifname',
                                   'timestamp_y'], errors='ignore') \
                    .rename(columns={'oif': 'ifname'})

            return arpdf['namespace hostname vrf ipAddress macaddr '
                         'vlan ifname timestamp'.split()]

        return arpdf

    def _find_l2_attach(self, addr_df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Find the L2 attachment point for this address

        Args:
            addr_df (pd.DataFrame): Dataframe with the address information
            **kwargs: Additional arguments to pass to the sqobject

        Returns:
            pd.DataFrame: Dataframe with the L2 attachment point information
        """

        # We'll need to resolve bond interfaces first
        l2_addr_df = addr_df

        lldp_df = get_sqobject('lldp')(context=self.ctxt).get(
            namespace=l2_addr_df.namespace.unique().tolist(),
            columns=['namespace', 'hostname', 'ifname', 'peerHostname',
                     'peerIfname'])

        if lldp_df.empty:
            return addr_df

        do_continue = True
        while do_continue:
            do_continue = False
            # Do not attempt to replace tmp_df with l2_addr_df and get
            # rid of do_contiue. For some weird reason, with pandas ver
            # 1.2.5, the explode line below hangs if we just use l2_addr_df

            tmp_df = self._find_bond_slaves(l2_addr_df)
            tmp_df['ifname'] = tmp_df.ifname.str.split(', ')
            tmp_df = tmp_df.explode('ifname')

            new_l2_addr_df = tmp_df.merge(lldp_df,
                                          on=['namespace',
                                              'hostname', 'ifname'],
                                          suffixes=['', '_y'])
            if not new_l2_addr_df.empty:
                new_l2_addr_df = new_l2_addr_df.drop(
                    columns=['timestamp_y', 'hostname', 'ifname'],
                    errors='ignore') \
                    .rename(columns={'peerHostname': 'hostname',
                                     'peerIfname': 'ifname'})
                macdf = get_sqobject('macs')(context=self.ctxt) \
                    .get(namespace=new_l2_addr_df.namespace.unique().tolist(),
                         macaddr=new_l2_addr_df.macaddr.unique().tolist(),
                         vlan=new_l2_addr_df.vlan.astype(
                             str).unique().tolist(),
                         columns=['namespace', 'hostname', 'vlan', 'macaddr', 'oif'])
                if not macdf.empty:
                    new_l2_addr_df = new_l2_addr_df.merge(
                        macdf,
                        on=['namespace', 'hostname', 'vlan', 'macaddr'],
                        suffixes=['', '_y'])
                    if not new_l2_addr_df.empty:
                        new_l2_addr_df = new_l2_addr_df \
                            .drop(columns=['ifname', 'mackey', 'timestamp_y',
                                           'flags', 'remoteVtepIp'],
                                  errors='ignore') \
                            .rename(columns={'oif': 'ifname'})
                        l2_addr_df = new_l2_addr_df
                        do_continue = True
            else:
                l2_addr_df = tmp_df
                do_continue = False

            if not new_l2_addr_df.empty:
                l2_addr_df = new_l2_addr_df
            else:
                l2_addr_df = tmp_df

        return l2_addr_df.drop_duplicates(
            subset=['namespace', 'hostname', 'ifname', 'macaddr', 'vlan'])
