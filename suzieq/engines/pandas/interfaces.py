from ipaddress import ip_network
import pandas as pd

from suzieq.exceptions import NoLLdpError
from suzieq.sqobjects.lldp import LldpObj
from suzieq.sqobjects.vlan import VlanObj
from .engineobj import SqEngineObject


class InterfacesObj(SqEngineObject):

    def aver(self, what="mtu-match", **kwargs) -> pd.DataFrame:
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
                                             "up": "up", "down": "down"})

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('interfaceCnt', 'ifname', 'count'),
        ]

        self._summarize_on_add_with_query = [
            ('devicesWithL2Cnt', 'master == "bridge"', 'hostname'),
            ('devicesWithVxlanCnt', 'type == "vxlan"', 'hostname'),
            ('ifDownCnt', 'state != "up"', 'ifname'),
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

        result_df = self.get(columns=columns, **kwargs) \
                        .query('ifname != "lo"')

        if not result_df.empty:
            result_df['assert'] = result_df.apply(
                lambda x: x['mtu'] == kwargs['matchval'])

        return result_df

    def _assert_interfaces(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine that validates MTU match for specified input"""
        columns = kwargs.pop('columns', [])

        columns = ["namespace", "hostname", "ifname", "state", "type", "mtu",
                   "vlan", "adminState", "ipAddressList", "ip6AddressList",
                   "speed", "master", "timestamp"]

        if_df = self.get(columns=columns, **kwargs)
        if if_df.empty:
            if_df['assert'] = 'fail'
            if_df['assertReason'] = 'No data'
            return if_df

        lldpobj = LldpObj(context=self.ctxt)
        vlanobj = VlanObj(context=self.ctxt)

        # can't pass all kwargs, because lldp acceptable arguements are
        # different than interface
        namespace = kwargs.get('namespace', None)
        hostname = kwargs.get('hostname', None)
        lldp_df = lldpobj.get(namespace=namespace,
                              hostname=hostname).query('peerIfname != "-"')

        # Get the VLAN info to ensure trunking ports are identical on both ends
        vlan_df = vlanobj.get(namespace=namespace, hostname=hostname)
        if not vlan_df.empty:
            vlan_df = vlan_df.explode('interfaces') \
                             .drop(columns=['vlanName'], errors='ignore') \
                             .rename(columns={'interfaces': 'ifname',
                                              'vlan': 'vlanList'})

            vlan_df = vlan_df.groupby(by=['namespace', 'hostname', 'ifname'])[
                'vlanList'].unique().reset_index().query('ifname != ""')

            # OK merge this list into the interface info
            if_df = if_df.merge(vlan_df,
                                on=['namespace', 'hostname', 'ifname'],
                                how='outer')
            if_df['vlanList'] = if_df['vlanList'] \
                .fillna({i: [] for i in if_df.index})

        if lldp_df.empty:
            if_df['assertReason'] = 'No LLDP peering info'
            if_df['assert'] = 'fail'
            return if_df

        # Now create a single DF where you get the MTU for the lldp
        # combo of (namespace, hostname, ifname) and the MTU for
        # the combo of (namespace, peerHostname, peerIfname) and then
        # pare down the result to the rows where the two MTUs don't match
        combined_df = (
            pd.merge(
                lldp_df,
                if_df,
                on=["namespace", "hostname", "ifname"],
                how="outer",
            )
            .dropna(how="any")
            .merge(
                if_df,
                left_on=["namespace", "peerHostname", "peerIfname"],
                right_on=["namespace", "hostname", "ifname"],
                how="outer",  suffixes=["", "Peer"],
            )
            .dropna(how="any")
            .drop(columns=["hostnamePeer", "ifnamePeer", "timestamp_x",
                           "mgmtIP", "description"])
        )

        if combined_df.empty:
            if_df['assertReason'] = 'No LLDP peering info'
            if_df['assert'] = 'fail'
            return if_df

        combined_df['assertReason'] = combined_df.apply(
            lambda x: []
            if (x['adminState'] == 'down' or
                (x['adminState'] == "up" and x['state'] == "up"))
            else ['Interface down'], axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: [] if x['mtu'] == x['mtuPeer'] else ['MTU mismatch'],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: [] if x['vlan'] == x['vlanPeer'] else ['PVID mismatch'],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: [] if x['speed'] == x['speedPeer']
            else ['Speed mismatch'],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: []
            if ((x['type'] == x['typePeer']) or
                (x['type'] == 'vlan' and x['typePeer'] == 'subinterface') or
                (x['type'].startswith('ether') and
                 x['typePeer'].startswith('ether')))
            else ['type mismatch'],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: []
            if ((len(x['ipAddressList']) == len(x['ipAddressListPeer'])) and
                ((len(x['ipAddressList']) == 0) or
                 (x['ipAddressList'][0].split('/')[1] == '32') or
                 (ip_network(x['ipAddressList'][0], strict=False) ==
                  ip_network(x['ipAddressListPeer'][0], strict=False))))
            else ['IP address mismatch'], axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: []
            if set(x['vlanList']) == set(x['vlanListPeer'])
            else ['VLAN set mismatch'], axis=1)

        combined_df['assert'] = combined_df.apply(
            lambda x: 'fail' if len(x.assertReason) else 'pass', axis=1)

        return combined_df[['namespace', 'hostname', 'ifname', 'state',
                            'peerHostname', 'peerIfname', 'assert',
                            'assertReason']]
