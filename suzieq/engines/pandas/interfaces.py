from ipaddress import ip_network
import pandas as pd
import numpy as np

from .engineobj import SqPandasEngine


class InterfacesObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'interfaces'

    def get(self, **kwargs):
        """Handling state outside of regular filters"""
        state = kwargs.pop('state', '')
        iftype = kwargs.pop('type', '')
        ifname = kwargs.get('ifname', '')
        vrf = kwargs.pop('vrf', '')
        master = kwargs.pop('master', [])

        if vrf:
            master.extend(vrf)

        if iftype and iftype != ["all"]:
            df = super().get(type=iftype, master=master, **kwargs)
        else:
            df = super().get(master=master, **kwargs)

        if df.empty:
            return df

        if state:
            if state.startswith('!'):
                df = df.query(f'state != "{state[1:]}"')
            else:
                df = df.query(f'state=="{state}"')

        if not (iftype or ifname) and 'type' in df.columns:
            return df.query('type != "internal"').reset_index(drop=True)
        else:
            return df.reset_index(drop=True)

    def aver(self, what="", **kwargs) -> pd.DataFrame:
        """Assert that interfaces are in good state"""

        if what == "mtu-value":
            result_df = self._assert_mtu_value(**kwargs)
        else:
            result_df = self._assert_interfaces(**kwargs)
        return result_df

    def summarize(self, **kwargs) -> pd.DataFrame:
        """Summarize interface information"""
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        # Loopback interfaces on Linux have "unknown" as state
        self.summary_df["state"] = self.summary_df['state'] \
                                       .map({"unknown": "up",
                                             "up": "up", "down": "down",
                                             "notConnected": "notConnected"})

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('interfaceCnt', 'ifname', 'count'),
        ]

        self._summarize_on_add_with_query = [
            ('devicesWithL2Cnt', 'master == "bridge"', 'hostname', 'nunique'),
            ('devicesWithVxlanCnt', 'type == "vxlan"', 'hostname'),
            ('ifDownCnt', 'state != "up" and adminState == "up"', 'ifname'),
            ('ifAdminDownCnt', 'adminState != "up"', 'ifname'),
            ('ifWithMultipleIPCnt', 'ipAddressList.str.len() > 1', 'ifname'),
        ]

        self._summarize_on_add_list_or_count = [
            ('uniqueMTUCnt', 'mtu'),
            ('uniqueIfTypesCnt', 'type'),
            ('speedCnt', 'speed'),
        ]

        self._summarize_on_add_stat = [
            ('ifChangesStat', 'type != "bond"', 'numChanges'),
        ]

        self._summarize_on_perdevice_stat = [
            ('ifPerDeviceStat', '', 'ifname', 'count')
        ]

        self._gen_summarize_data()

        # The rest of the summary generation is too specific to interfaces
        original_summary_df = self.summary_df
        self.summary_df = original_summary_df.explode(
            'ipAddressList').dropna(how='any')

        if not self.summary_df.empty:
            self.nsgrp = self.summary_df.groupby(by=["namespace"])
            self._add_field_to_summary(
                'ipAddressList', 'nunique', 'uniqueIPv4AddrCnt')
        else:
            self._add_constant_to_summary('uniqueIPv4AddrCnt', 0)
        self.summary_row_order.append('uniqueIPv4AddrCnt')

        self.summary_df = original_summary_df \
            .explode('ip6AddressList') \
            .dropna(how='any') \
            .query('~ip6AddressList.str.startswith("fe80:")')

        if not self.summary_df.empty:
            self.nsgrp = self.summary_df.groupby(by=["namespace"])
            self._add_field_to_summary(
                'ip6AddressList', 'nunique', 'uniqueIPv6AddrCnt')
        else:
            self._add_constant_to_summary('uniqueIPv6AddrCnt', 0)
        self.summary_row_order.append('uniqueIPv6AddrCnt')

        self._post_summarize(check_empty_col='interfaceCnt')
        return self.ns_df.convert_dtypes()

    def _assert_mtu_value(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine to match MTU value"""

        columns = ["namespace", "hostname", "ifname", "state", "mtu",
                   "timestamp"]

        matchval = kwargs.pop('matchval', [])
        status = kwargs.pop('status', '')

        matchval = [int(x) for x in matchval]

        result_df = self.get(columns=columns, **kwargs) \
                        .query('ifname != "lo"')

        if not result_df.empty:
            result_df['status'] = result_df.apply(
                lambda x, matchval: 'pass' if x['mtu'] in matchval else 'fail',
                axis=1, args=(matchval,))

        if status == "fail":
            result_df = result_df.query('status == "fail"')
        elif status == "pass":
            result_df = result_df.query('status == "pass"')

        if not result_df.empty:
            return result_df.rename(columns={'status': 'assert'})
        else:
            return result_df

    def _assert_interfaces(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine that validates MTU match for specified input"""
        columns = kwargs.pop('columns', [])
        status = kwargs.pop('status', 'all')
        ignore_missing_peer = kwargs.pop('ignore_missing_peer', False)

        def _check_field(x, fld1, fld2, reason):
            if x.skipIfCheck or x.indexPeer < 0:
                return []

            if x[fld1] == x[fld2]:
                return []
            return reason

        def _check_ipaddr(x, fld1, fld2, reason):
            # If we have no peer, don't check
            if x.skipIfCheck or x.indexPeer < 0:
                return []

            if len(x[fld1]) != len(x[fld2]):
                return reason

            if (len(x[fld1]) != 0):
                if (x[fld1][0].split('/')[1] == "32" or
                    (ip_network(x[fld1][0], strict=False) ==
                        ip_network(x[fld2][0], strict=False))):
                    return []
            else:
                return []

            return reason

        columns = ["namespace", "hostname", "ifname", "state", "type", "mtu",
                   "vlan", "adminState", "ipAddressList", "ip6AddressList",
                   "speed", "master", "timestamp", "reason"]

        if_df = self.get(columns=columns,
                         type=['ethernet', 'bond_slave', 'subinterface',
                               'vlan', 'bond'],
                         state='up',
                         **kwargs)
        if if_df.empty:
            if status != 'pass':
                if_df['assert'] = 'fail'
                if_df['assertReason'] = 'No data'

            return if_df

        # Map subinterface into parent interface
        if_df['pifname'] = if_df.apply(
            lambda x: x['ifname'].split('.')[0]
            if (x.type == 'subinterface') or (x.type == 'vlan')
            else x['ifname'], axis=1)

        # Thanks for Junos, remove all the useless parent interfaces
        # if we have a .0 interface since thats the real deal
        del_iflist = if_df.apply(lambda x: x.pifname
                                 if x['ifname'].endswith('.0') else '',
                                 axis=1) \
            .unique().tolist()

        if_df['type'] = if_df.apply(lambda x: 'ethernet'
                                    if x['ifname'].endswith('.0')
                                    else x['type'], axis=1)

        if_df = if_df.query(f'~ifname.isin({del_iflist})').reset_index()
        if_df['ifname'] = if_df.apply(
            lambda x: x['ifname'] if not x['ifname'].endswith('.0')
            else x['pifname'], axis=1)

        lldpobj = self._get_table_sqobj('lldp')
        vlanobj = self._get_table_sqobj('vlan')
        mlagobj = self._get_table_sqobj('mlag')

        # can't pass all kwargs, because lldp acceptable arguements are
        # different than interface
        namespace = kwargs.get('namespace', None)
        hostname = kwargs.get('hostname', None)
        lldp_df = lldpobj.get(namespace=namespace, hostname=hostname) \
                         .query('peerIfname != "-"')

        mlag_df = mlagobj.get(namespace=namespace, hostname=hostname)
        if not mlag_df.empty:
            mlag_peerlinks = set(mlag_df
                                 .groupby(by=['namespace', 'hostname',
                                              'peerLink'])
                                 .groups.keys())
        else:
            mlag_peerlinks = set()

        # Get the VLAN info to ensure trunking ports are identical on both ends
        vlan_df = vlanobj.get(namespace=namespace, hostname=hostname)
        if not vlan_df.empty and not (vlan_df.interfaces.str.len() == 0).all():
            vlan_df = vlan_df.explode('interfaces') \
                             .drop(columns=['vlanName'], errors='ignore') \
                             .rename(columns={'interfaces': 'ifname',
                                              'vlan': 'vlanList'})

            vlan_df = vlan_df.groupby(by=['namespace', 'hostname', 'ifname'])[
                'vlanList'].unique().reset_index().query('ifname != ""')

            # OK merge this list into the interface info
            if_df = if_df.merge(vlan_df,
                                on=['namespace', 'hostname', 'ifname'],
                                how='left')
            if not if_df.empty:
                if_df['vlanList'] = if_df['vlanList'] \
                    .fillna({i: [] for i in if_df.index})

        if 'vlanList' not in if_df.columns:
            if_df['vlanList'] = []

        if lldp_df.empty:
            if status != 'pass':
                if_df['assertReason'] = 'No LLDP peering info'
                if_df['assert'] = 'fail'

            return if_df

        # Now create a single DF where you get the MTU for the lldp
        # combo of (namespace, hostname, ifname) and the MTU for
        # the combo of (namespace, peerHostname, peerIfname) and then
        # pare down the result to the rows where the two MTUs don't match
        idf = (
            pd.merge(
                if_df,
                lldp_df,
                left_on=["namespace", "hostname", "pifname"],
                right_on=['namespace', 'hostname', 'ifname'],
                how="outer",
            )
            .drop(columns=['ifname_y', 'timestamp_y'])
            .rename({'ifname_x': 'ifname', 'timestamp_x': 'timestamp'}, axis=1)
        )
        idf_nonsubif = idf.query('~type.isin(["subinterface", "vlan"])')
        idf_subif = idf.query('type.isin(["subinterface", "vlan"])')

        # Replace the bond_slave port interface with the bond interface

        idf_nonsubif = idf_nonsubif.merge(
            idf_nonsubif,
            left_on=["namespace", "peerHostname", "peerIfname"],
            right_on=['namespace', 'hostname', 'ifname'],
            how="outer", suffixes=["", "Peer"])

        idf_subif = idf_subif.merge(
            idf_subif,
            left_on=["namespace", "peerHostname", "peerIfname", 'vlan'],
            right_on=['namespace', 'hostname', 'pifname', 'vlan'],
            how="outer", suffixes=["", "Peer"])

        combined_df = pd.concat(
            [idf_subif, idf_nonsubif]).reset_index(drop=True)

        combined_df = combined_df \
            .drop(columns=["hostnamePeer", "pifnamePeer",
                           "mgmtIP", "description"]) \
            .dropna(subset=['hostname', 'ifname']) \
            .drop_duplicates(subset=['namespace', 'hostname', 'ifname'])

        if combined_df.empty:
            if status != 'pass':
                if_df['assertReason'] = 'No LLDP peering info'
                if_df['assert'] = 'fail'

            return if_df

        combined_df = combined_df.fillna(
            {'mtuPeer': 0, 'speedPeer': 0, 'typePeer': '',
             'peerHostname': '', 'peerIfname': '', 'indexPeer': -1})
        for fld in ['ipAddressListPeer', 'ip6AddressListPeer', 'vlanListPeer']:
            combined_df[fld] = combined_df[fld] \
                .apply(lambda x: x if isinstance(x, np.ndarray) else [])

        combined_df['assertReason'] = combined_df.apply(
            lambda x: []
            if (x['adminState'] == 'down' or
                (x['adminState'] == "up" and x['state'] == "up"))
            else [x.reason or "Interface Down"], axis=1)

        known_hosts = set(combined_df.groupby(by=['namespace', 'hostname'])
                          .groups.keys())
        # Mark interfaces that can be skippedfrom checking because you cannot
        # find a peer
        combined_df['skipIfCheck'] = combined_df.apply(
            lambda x:
            True if ((x.master == 'bridge') or
                     (x.type in ['bond_slave', 'vlan'])) else False,
            axis=1)

        combined_df['indexPeer'] = combined_df.apply(
            lambda x, kh: x.indexPeer
            if (x.namespace, x.hostname) in kh else -2,
            args=(known_hosts,), axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: ['No Peer Found']
            if x.indexPeer == -1 and not x.skipIfCheck else [],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: ['Unpolled Peer']
            if x.indexPeer == -2 and not x.skipIfCheck else [],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: _check_field(x, 'mtu', 'mtuPeer', ['MTU mismatch']),
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: _check_field(
                x, 'speed', 'speedPeer', ['Speed mismatch']),
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: []
            if (x.indexPeer < 0 or
                ((x['type'] == x['typePeer']) or
                 (x['type'] == 'vlan' and x['typePeer'] == 'subinterface') or
                    (x['type'].startswith('ether') and
                     x['typePeer'].startswith('ether'))))
            else ['type mismatch'],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x:
            _check_ipaddr(x, 'ipAddressList', 'ipAddressListPeer',
                          ['IP address mismatch']), axis=1)

        # We ignore MLAG peerlinks mainly because of NXOS erroneous output.
        # NXOS displays the VLANs associated with an interface via show vlan
        # which is then further pruned out by vPC. This pruned out list needs
        # to be extracted from the vPC output and used for the peerlink
        # instead of the output of show vlan for that interface. Since most
        # platforms perform their own MLAG consistency checks, we can skip
        # doing VLAN consistency check on the peerlink.
        # TODO: A better checker for MLAG peerlinks if needed at a later time.

        combined_df['assertReason'] += combined_df.apply(
            lambda x, mlag_peerlinks: []
            if ((x.indexPeer > 0 and
                ((x.namespace, x.hostname, x.master) not in mlag_peerlinks) and
                 (set(x['vlanList']) == set(x['vlanListPeer']))) or
                ((x.indexPeer < 0) or
                ((x.namespace, x.hostname, x.master) in mlag_peerlinks)))
            else ['VLAN set mismatch'], args=(mlag_peerlinks,), axis=1)

        if ignore_missing_peer:
            combined_df['check'] = combined_df.apply(
                lambda x: 'fail'
                if (len(x.assertReason) and
                    (x.assertReason[0] != 'No Peer Found'))
                else 'pass', axis=1)
        else:
            combined_df['check'] = combined_df.apply(
                lambda x: 'fail' if (len(x.assertReason)) else 'pass', axis=1)

        if status == "fail":
            combined_df = combined_df.query('check == "fail"').reset_index()
        elif status == "pass":
            combined_df = combined_df.query('check == "pass"').reset_index()

        return combined_df[['namespace', 'hostname', 'ifname', 'state',
                            'peerHostname', 'peerIfname', 'check',
                            'assertReason', 'timestamp']] \
            .rename({'check': 'assert'}, axis=1)
