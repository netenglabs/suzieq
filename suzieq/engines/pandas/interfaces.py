import pandas as pd

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
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields
        kwargs.pop("columns", None)

        df = self.get_valid_df(self.iobj._table, sort_fields,
                               columns=['*'], **kwargs)

        if df.empty:
            return df

        nsgrp = df.groupby(by=["namespace"])
        ns = {i: {} for i in nsgrp.groups.keys()}

        hosts_per_ns = nsgrp["hostname"].nunique()
        {ns[i].update({'hosts': hosts_per_ns[i]}) for i in hosts_per_ns.keys()}

        ifs_per_ns = nsgrp["ifname"].count()
        {ns[i].update({'interfaces': ifs_per_ns[i]})
         for i in ifs_per_ns.keys()}

        median_ifs_per_hostns = df.groupby(by=["namespace", "hostname"])[
            "ifname"].count().groupby("namespace").median()
        {ns[i].update({'medIfPerHost': median_ifs_per_hostns[i]})
         for i in median_ifs_per_hostns.keys()}

        hosts_l2_per_ns = df.query("type == 'vlan' or "
                                   "type == 'bridge'") \
            .groupby(by=["namespace"])[
            "hostname"].nunique()
        {ns[i].update({'hostsWithL2': hosts_l2_per_ns[i]})
         for i in hosts_l2_per_ns.keys()}

        has_vxlan_perns = df.query("type == 'vxlan'") \
                            .groupby(by=["namespace"])["hostname"].count()
        {ns[i].update({'hasVxlan': (has_vxlan_perns[i] > 0)})
         for i in has_vxlan_perns.keys()}

        mtu_list_perns = nsgrp["mtu"].unique()
        {ns[i].update({'mtuList': mtu_list_perns[i]})
         for i in mtu_list_perns.keys()}

        downif_per_ns = df.query('state != "up"') \
                          .groupby(by=["namespace"])["ifname"].count()

        {ns[i].update({'downPortCount': downif_per_ns[i]})
         for i in downif_per_ns.keys()}

        med_linkif_transitions = df[df.type.str.startswith('ether')] \
            .groupby(by=["namespace"])["numChanges"].median()
        {ns[i].update({'medianIfChanges': med_linkif_transitions[i]})
         for i in med_linkif_transitions.keys()}

        # Eliminate all the fields without the desired namespace if provided
        # As described earlier this is only required for routes
        namespaces = set(tuple(kwargs.get("namespace", [])))
        if namespaces:
            nskeys = set(tuple(ns.keys()))
            deselect_keys = nskeys - namespaces
            if deselect_keys:
                for key in deselect_keys:
                    del ns[key]

        return(pd.DataFrame(ns).convert_dtypes())

    def _assert_mtu_value(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine to match MTU value"""
        columns = ["namespace", "hostname",
                   "ifname", "state", "mtu", "timestamp"]
        sort_fields = ["namespace", "hostname", "ifname"]

        query_df = self.get_valid_df(
            "interfaces",
            sort_fields,
            hostname=kwargs.get("hostname", []),
            namespace=kwargs.get("namespace", []),
            columns=columns,
            ifname=kwargs.get("ifname", []),
        ).query('(abs(mtu - {}) > 40) and (ifname != "lo")'.format(kwargs["matchval"]))

        return query_df

    def _assert_mtu_match(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine that validates MTU match for specified input"""
        lldpobj = LldpObj(context=self.ctxt)
        lldp_df = lldpobj.get(**kwargs)

        if lldp_df.empty:
            print("No Valid LLDP info found, Asserting MTU not possible")
            return pd.DataFrame(columns=["namespace", "hostname"])

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
            print("No Valid LLDP info found, Asserting MTU not possible")
            return pd.DataFrame(columns=columns)

        # Now create a single DF where you get the MTU for the lldp
        # combo of (namespace, hostname, ifname) and the MTU for
        # the combo of (namespace, peerHostname, peerIfname) and then
        # pare down the result to the rows where the two MTUs don't match
        query_df = (
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
            .query("mtu_x != mtu_y")
            .drop(columns=["hostname_y", "ifname_y"])
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

        return query_df

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
