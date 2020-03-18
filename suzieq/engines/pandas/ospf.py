from ipaddress import IPv4Network
import pandas as pd

from suzieq.utils import SchemaForTable
from suzieq.sqobjects.lldp import LldpObj
from suzieq.engines.pandas.engineobj import SqEngineObject


class OspfObj(SqEngineObject):
    def get(self, **kwargs):

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        table = "ospfNbr"
        if "type" in kwargs:
            if kwargs.get("type", "interface") == "interface":
                table = "ospfIf"
            del kwargs["type"]

        df = self.get_valid_df(table, sort_fields, **kwargs)
        return df

    def summarize(self, **kwargs):
        """Describe the data"""
        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        table = "ospfNbr"
        if "type" in kwargs:
            if kwargs.get("type", "interface") == "interface":
                table = "ospfIf"
            del kwargs["type"]

        df = self.get_valid_df(table, sort_fields, **kwargs)

        if not df.empty:
            if kwargs.get("groupby"):
                return df.groupby(kwargs["groupby"]).agg(lambda x: x.unique().tolist())
            else:
                return df.describe(include="all").fillna("-")

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

        ospf_df = self.get_valid_df("ospfIf", sort_fields, columns=columns, **kwargs)
        if ospf_df.empty:
            return pd.DataFrame(columns=columns)

        df = (
            ospf_df.ix[ospf_df["routerId"] != ""]
            .groupby(["routerId"], as_index=False)[["hostname"]]
            .agg(lambda x: x.unique().tolist())
        )

        dup_rtrid_df = df[df["hostname"].map(len) > 1]

        bad_ospf_df = ospf_df.query('nbrCount < 1 and passive != "True"')

        lldpobj = LldpObj(context=self.ctxt)
        lldp_df = lldpobj.get(
            namespace=kwargs.get("namespace", ""),
            hostname=kwargs.get("hostname", ""),
            ifname=kwargs.get("ifname", ""),
        )
        if lldp_df.empty:
            print("No LLDP info, unable to ascertain cause of OSPF failure")
            return bad_ospf_df

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
        df1 = (
            pd.merge(
                lldp_df, ospf_df[use_cols], on=["namespace", "hostname", "ifname"]
            )
            .dropna(how="any")
            .merge(
                ospf_df[use_cols],
                how="outer",
                left_on=["namespace", "peerHostname", "peerIfname"],
                right_on=["namespace", "hostname", "ifname"],
            )
            .dropna(how="any")
        )

        if df1.empty:
            return dup_rtrid_df

        # Now start comparing the various parameters
        df1["reason"] = tuple([tuple() for _ in range(len(df1))])
        df1["reason"] += df1.apply(
            lambda x: tuple(["subnet mismatch"])
            if (
                (x["isUnnumbered_x"] != x["isUnnumbered_y"])
                and (
                    IPv4Network(x["ipAddress_x"], strict=False)
                    != IPv4Network(x["ipAddress_y"], strict=False)
                )
            )
            else tuple(),
            axis=1,
        )
        df1["reason"] += df1.apply(
            lambda x: tuple(["area mismatch"])
            if (x["area_x"] != x["area_y"] and x["areaStub_x"] != x["areaStub_y"])
            else tuple(),
            axis=1,
        )
        df1["reason"] += df1.apply(
            lambda x: tuple(["Hello timers mismatch"])
            if x["helloTime_x"] != x["helloTime_y"]
            else tuple(),
            axis=1,
        )
        df1["reason"] += df1.apply(
            lambda x: tuple(["Dead timer mismatch"])
            if x["deadTime_x"] != x["deadTime_y"]
            else tuple(),
            axis=1,
        )
        df1["reason"] += df1.apply(
            lambda x: tuple(["network type mismatch"])
            if x["networkType_x"] != x["networkType_y"]
            else tuple(),
            axis=1,
        )
        df1["reason"] += df1.apply(
            lambda x: tuple(["passive config mismatch"])
            if x["passive_x"] != x["passive_y"]
            else tuple(),
            axis=1,
        )
        df1["reason"] += df1.apply(
            lambda x: tuple(["vrf mismatch"]) if x["vrf_x"] != x["vrf_y"] else tuple(),
            axis=1,
        )

        # Add back the duplicate routerid stuff
        def is_duprtrid(x):
            for p in dup_rtrid_df["hostname"].tolist():
                if x["hostname_x"] in p:
                    x["reason"] = tuple(["duplicate routerId:{}".format(p)])

            return x

        df2 = (
            df1.apply(is_duprtrid, axis=1)
            .drop_duplicates(subset=["namespace", "hostname_x"], keep="last")
            .query("reason != tuple()")[["namespace", "hostname_x", "vrf_x", "reason"]]
        )
        df1 = pd.concat([df1, df2], sort=False)
        return (
            (
                df1.rename(
                    index=str,
                    columns={
                        "hostname_x": "hostname",
                        "ifname_x": "ifname",
                        "vrf_x": "vrf",
                    },
                )[["namespace", "hostname", "ifname", "vrf", "reason"]]
            )
            .query("reason != tuple()")
            .fillna("-")
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
