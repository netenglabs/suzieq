from ipaddress import IPv4Network
import pandas as pd

from suzieq.exceptions import NoLLdpError
from suzieq.utils import SchemaForTable
from suzieq.sqobjects.lldp import LldpObj
from suzieq.engines.pandas.engineobj import SqEngineObject


def _choose_table(**kwargs):
    table = "ospfNbr"
    if "type" in kwargs:
        if kwargs.get("type", "interface") == "interface":
            table = "ospfIf"
        del kwargs["type"]
    return table, kwargs


class OspfObj(SqEngineObject):
    def get(self, **kwargs):

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        table, kwargs = _choose_table(**kwargs)

        df = self.get_valid_df(table, sort_fields, **kwargs)
        return df

    def summarize(self, **kwargs):
        """Describe the data"""

        table, kwargs = _choose_table(**kwargs)
        self._init_summarize(table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        if table == 'ospfNbr':
            self._add_field_to_summary('hostname', 'count', 'rows')
            self._add_field_to_summary('hostname', 'nunique', 'hosts')
            for field in ['vrf', 'area', 'nbrPrio', 'state', 'peerRouterId']:
                self._add_list_or_count_to_summary(field)

            up_time = self.summary_df.query("state == 'full'") \
                .groupby(by=["namespace"])["lastChangeTime"]
            self._add_stats_to_summary(up_time, 'lastChangeTime')

            for field in ['numChanges', 'lsaRetxCnt']:
                field_stat = self.nsgrp[field]
                self._add_stats_to_summary(field_stat, field)

            # order data.
            self.summary_row_order = ['hosts', 'rows', 'area', 'vrf', 'state',
                                      'nbrPrio', 'peerRouterId', 'lastChangeTime',
                                      'numChanges', 'lsaRetxCnt']

        else:
            for field in ['helloTime', 'cost', 'deadTime', 'retxTime', 'vrf',
                          'state', 'areaStub', 'area', 'passive',
                          'nbrCount', 'networkType', 'isUnnumbered']:
                self._add_list_or_count_to_summary(field)
            self._add_field_to_summary('hostname', 'count', 'rows')

            self.summary_row_order = ['rows', 'state', 'nbrCount', 'isUnnumbered',
                                      'area', 'vrf', 'networkType', 'passive', 'areaStub',
                                      'cost', 'helloTime', 'deadTime', 'retxTime']

        # TODO
        # need to do something about loopbacks without address or something

        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def unique(self, **kwargs):
        table, kwargs = _choose_table(**kwargs)
        self.iobj._table = table
        return super().unique(**kwargs)

    def aver(self, **kwargs):
        """Assert that the OSPF state is OK"""

        columns = [
            "namespace",
            "hostname",
            "vrf",
            "ifname",
            "routerId",
            "helloTime",
            "deadTime",
            "passive",
            "ipAddress",
            "isUnnumbered",
            "areaStub",
            "networkType",
            "timestamp",
            "area",
            "nbrCount",
        ]
        sort_fields = ["namespace", "hostname", "ifname", "vrf"]

        ospf_df = self.get_valid_df(
            "ospfIf", sort_fields, columns=columns, **kwargs)
        if ospf_df.empty:
            return pd.DataFrame(columns=columns)

        ospf_df["assertReason"] = [[] for _ in range(len(ospf_df))]
        df = (
            ospf_df[ospf_df["routerId"] != ""]
            .groupby(["routerId", "namespace"], as_index=False)[["hostname", "namespace"]]
            .agg(lambda x: x.unique().tolist())
        ).dropna(how='any')

        # df is a dataframe with each row containing the routerId and the
        # corresponding list of hostnames with that routerId. In a good
        # configuration, the list must have exactly one entry
        ospf_df['assertReason'] = (
            ospf_df.merge(df, on=["routerId"], how="outer")
            .apply(lambda x: ["duplicate routerId {}".format(
                x["hostname_y"])]
                if len(x['hostname_y']) != 1 else [], axis=1))

        # Now  peering match
        lldpobj = LldpObj(context=self.ctxt)
        lldp_df = lldpobj.get(
            namespace=kwargs.get("namespace", ""),
            hostname=kwargs.get("hostname", ""),
            ifname=kwargs.get("ifname", ""),
            columns=["namespace", "hostname", "ifname", "peerHostname",
                     "peerIfname"]
        )
        if lldp_df.empty:
            raise NoLLdpError("No LLDP info found")

        # Create a single massive DF with fields populated appropriately
        use_cols = [
            "namespace",
            "routerId",
            "hostname",
            "vrf",
            "ifname",
            "helloTime",
            "deadTime",
            "passive",
            "ipAddress",
            "areaStub",
            "isUnnumbered",
            "networkType",
            "area",
        ]

        int_df = ospf_df[use_cols].merge(lldp_df,
                                         on=["namespace", "hostname",
                                             "ifname"]) \
            .dropna(how="any")

        ospf_df = ospf_df.merge(int_df,
                                left_on=["namespace", "hostname", "ifname"],
                                right_on=["namespace", "peerHostname",
                                          "peerIfname"]) \
            .dropna(how="any")

        # Now start comparing the various parameters
        ospf_df["assertReason"] += ospf_df.apply(
            lambda x: ["subnet mismatch"]
            if (
                (x["isUnnumbered_x"] != x["isUnnumbered_y"])
                and (
                    IPv4Network(x["ipAddress_x"], strict=False)
                    != IPv4Network(x["ipAddress_y"], strict=False)
                )
            )
            else [],
            axis=1,
        )
        ospf_df["assertReason"] += ospf_df.apply(
            lambda x: ["area mismatch"]
            if (x["area_x"] != x["area_y"] and x["areaStub_x"] != x["areaStub_y"])
            else [],
            axis=1,
        )
        ospf_df["assertReason"] += ospf_df.apply(
            lambda x: ["Hello timers mismatch"]
            if x["helloTime_x"] != x["helloTime_y"]
            else [],
            axis=1,
        )
        ospf_df["assertReason"] += ospf_df.apply(
            lambda x: ["Dead timer mismatch"]
            if x["deadTime_x"] != x["deadTime_y"]
            else [],
            axis=1,
        )
        ospf_df["assertReason"] += ospf_df.apply(
            lambda x: ["network type mismatch"]
            if x["networkType_x"] != x["networkType_y"]
            else [],
            axis=1,
        )
        ospf_df["assertReason"] += ospf_df.apply(
            lambda x: ["passive config mismatch"]
            if x["passive_x"] != x["passive_y"]
            else [],
            axis=1,
        )
        ospf_df["assertReason"] += ospf_df.apply(
            lambda x: ["vrf mismatch"] if x["vrf_x"] != x["vrf_y"] else [],
            axis=1,
        )

        # Fill up a single assert column now indicating pass/fail
        ospf_df['assert'] = ospf_df.apply(lambda x: 'pass'
                                          if not len(x['assertReason'])
                                          else 'fail', axis=1)

        return (
            ospf_df.rename(
                index=str,
                columns={
                    "hostname_x": "hostname",
                    "ifname_x": "ifname",
                    "vrf_x": "vrf",
                },
            )[["namespace", "hostname", "ifname", "vrf", "assert",
               "assertReason"]].explode(column='assertReason')
            .fillna({'assertReason': '-'})
        )

    def top(self, what="transitions", n=5, **kwargs) -> pd.DataFrame:
        """Get the list of top stuff about OSPF"""

        if "columns" in kwargs:
            columns = kwargs["columns"]
            del kwargs["columns"]
        else:
            columns = ["default"]

        table_schema = SchemaForTable('ospfNbr', self.schemas)
        columns = table_schema.get_display_fields(columns)

        if "numChanges" not in columns:
            columns.insert(-2, "numChanges")

        df = self.get(columns=columns, **kwargs)
        if df.empty:
            return df

        return df.nlargest(n, columns=["numChanges"], keep="all").head(n=n)
