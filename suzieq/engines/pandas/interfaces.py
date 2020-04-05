import pandas as pd

from suzieq.exceptions import NoLLdpError
from suzieq.utils import SchemaForTable
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

    def top(self, what="transitions", n=5, **kwargs) -> pd.DataFrame:
        """Get the list of top link changes"""
        result_df = self._top_link_transitions(n, **kwargs)

        return result_df

    def summarize(self, **kwargs) -> pd.DataFrame:
        """Summarize interface information"""
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        ifs_per_hostns = self.summary_df.groupby(by=["namespace", "hostname"])[
            "ifname"].count().groupby("namespace")

        hosts_l2_per_ns = self.summary_df.query("type == 'vlan' or "
                                                "type == 'bridge'") \
            .groupby(by=["namespace"])[
            "hostname"].nunique()

        has_vxlan_perns = self.summary_df.query("type == 'vxlan'") \
            .groupby(by=["namespace"])["hostname"].count()
        downif_per_ns = self.summary_df.query('state != "up"') \
            .groupby(by=["namespace"])["ifname"].count()

        linkif_transitions = self.summary_df[self.summary_df.type.str.startswith('ether')] \
            .groupby(by=["namespace"])["numChanges"]

        # num  of interfaces that have more than one IP
        mt1_ip_per_interface = self.summary_df[self.summary_df.apply(
            lambda x: len(x['ipAddressList']) > 1,
            axis=1)].groupby(by=['namespace'])['ifname'].count()
        self._add_field_to_summary('hostname', 'nunique', 'hosts')
        self._add_field_to_summary('ifname', 'count', 'rows')
        for field in ['mtu', 'state', 'type']:
            self._add_list_or_count_to_summary(field)

        self._add_stats_to_summary(ifs_per_hostns, 'ifPerHost')
        self._add_stats_to_summary(linkif_transitions, 'ifChanges')

        for i in self.ns.keys():
            self.ns[i].update({'hostsWithL2': hosts_l2_per_ns[i]})
            self.ns[i].update({'hasVxlan': (has_vxlan_perns[i] > 0)})
            self.ns[i].update({'downPortCount': downif_per_ns[i]})
            self.ns[i].update({'mtOneIpPerInterface': mt1_ip_per_interface[i]})

        original_summary_df = self.summary_df
        self.summary_df = original_summary_df.explode(
            'ipAddressList').dropna(how='any')

        if not self.summary_df.empty:
            self.nsgrp = self.summary_df.groupby(by=["namespace"])
            self._add_field_to_summary(
                'ipAddressList', 'nunique', 'ipV4Addresses')

        self.summary_df = original_summary_df.explode(
            'ip6AddressList').dropna(how='any')

        if not self.summary_df.empty:
            self.nsgrp = self.summary_df.groupby(by=["namespace"])
            self._add_field_to_summary(
                'ip6AddressList', 'nunique', 'ipV6Addresses')

        self.summary_row_order = ['hosts', 'rows', 'ifPerHost',
                                  'hostsWithL2', 'hasVxlan', 'mtu', 'type',
                                  'ipV4Addresses', 'ipV6Addresses', 'mtOneIpPerInterface',
                                  'downPortCount', 'state', 'ifChanges']

        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def _assert_mtu_value(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine to match MTU value"""
        columns = ["namespace", "hostname",
                   "ifname", "state", "mtu", "timestamp"]
        sort_fields = ["namespace", "hostname", "ifname"]

        result_df = self.get_valid_df(
            "interfaces",
            sort_fields,
            hostname=kwargs.get("hostname", []),
            namespace=kwargs.get("namespace", []),
            columns=columns,
            ifname=kwargs.get("ifname", []),
        ).query('ifname != "lo"')

        if not result_df.empty:
            result_df['assert'] = result_df.apply(
                lambda x: x['mtu'] == kwargs['matchval'])

        return result_df

    def _assert_mtu_match(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine that validates MTU match for specified input"""
        lldpobj = LldpObj(context=self.ctxt)
        lldp_df = lldpobj.get(**kwargs)

        if lldp_df.empty:
            raise NoLLdpError("No Valid LLDP info found")

        columns = ["namespace", "hostname",
                   "ifname", "state", "mtu", "timestamp"]
        if_df = self.get_valid_df(
            "interfaces",
            self.sort_fields,
            hostname=kwargs.get("hostname", []),
            namespace=kwargs.get("namespace", []),
            columns=columns,
            ifname=kwargs.get("ifname", []),
        )
        if if_df.empty:
            return pd.DataFrame(columns=columns+["assert"])

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
            return combined_df

        combined_df['assert'] = combined_df.apply(lambda x: 'pass'
                                                  if x['mtu'] == x['peerMtu']
                                                  else 'fail', axis=1)

        return combined_df

    def _top_link_transitions(self, n, **kwargs):
        """Workhorse routine to return top n link transition links"""

        if "columns" in kwargs:
            columns = kwargs["columns"]
            del kwargs["columns"]
        else:
            columns = ["default"]

        table_schema = SchemaForTable(self.table, self.schemas)
        columns = table_schema.get_display_fields(columns)

        if "numChanges" not in columns:
            columns.insert(-2, "numChanges")

        if "type" not in kwargs:
            # On Linux there are all kinds of link transitions on non-physical
            # links. Lets filter them out to prevent polluting the information.
            kwargs["type"] = "ether"

        df = self.get(columns=columns, **kwargs)
        if df.empty:
            return df

        return df.nlargest(n, columns=["numChanges"], keep="all").head(n=n)
