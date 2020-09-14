import pandas as pd

from suzieq.exceptions import NoLLdpError
from suzieq.sqobjects.lldp import LldpObj
from .engineobj import SqEngineObject


class InterfacesObj(SqEngineObject):

    def aver(self, what="mtu-match", **kwargs) -> pd.DataFrame:
        """Assert that interfaces are in good state"""
        if what == "mtu-match":
            result_df = self._assert_mtu_match(**kwargs)
        elif what == "mtu-value":
            result_df = self._assert_mtu_value(**kwargs)

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

    def _assert_mtu_match(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine that validates MTU match for specified input"""
        columns = kwargs.pop('columns', [])

        columns = ["namespace", "hostname", "ifname", "state", "type", "mtu",
                   "timestamp"]

        type = kwargs.pop('type', 'ethernet')

        if_df = self.get(columns=columns, type=type, **kwargs)
        if if_df.empty:
            return pd.DataFrame(columns=columns+["assert"])

        lldpobj = LldpObj(context=self.ctxt)
        lldp_df = lldpobj.get(**kwargs).query('peerIfname != "-"')

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
                if_df[["namespace", "hostname", "ifname", "mtu"]],
                on=["namespace", "hostname", "ifname"],
                how="outer",
            )
            .dropna(how="any")
            .merge(
                if_df[["namespace", "hostname", "ifname", "mtu"]],
                left_on=["namespace", "peerHostname", "peerIfname"],
                right_on=["namespace", "hostname", "ifname"],
                how="outer",
            )
            .dropna(how="any")
            .drop(columns=["hostname_y", "ifname_y", "mgmtIP", "description"])
            .rename(
                index=str,
                columns={
                    "hostname_x": "hostname",
                    "ifname_x": "ifname",
                    "mtu_x": "mtu",
                    "mtu_y": "peerMtu",
                },
            )
        )

        if combined_df.empty:
            if_df['assertReason'] = 'No LLDP peering info'
            if_df['assert'] = 'fail'
            return if_df

        combined_df['assert'] = combined_df.apply(lambda x: 'pass'
                                                  if x['mtu'] == x['peerMtu']
                                                  else 'fail', axis=1)

        return combined_df
