#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

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

    def _assert_mtu_value(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine to match MTU value"""
        columns = ["datacenter", "hostname", "ifname", "state", "mtu", "timestamp"]
        sort_fields = ["datacenter", "hostname", "ifname"]

        query_df = self.get_valid_df(
            "interfaces",
            sort_fields,
            hostname=kwargs.get("hostname", []),
            datacenter=kwargs.get("datacenter", []),
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
            return pd.DataFrame(columns=["datacenter", "hostname"])

        columns = ["datacenter", "hostname", "ifname", "state", "mtu", "timestamp"]
        if_df = self.get_valid_df(
            "interfaces",
            self.sort_fields,
            hostname=kwargs.get("hostname", []),
            datacenter=kwargs.get("datacenter", []),
            columns=columns,
            ifname=kwargs.get("ifname", []),
        )
        if if_df.empty:
            print("No Valid LLDP info found, Asserting MTU not possible")
            return pd.DataFrame(columns=columns)

        # Now create a single DF where you get the MTU for the lldp
        # combo of (datacenter, hostname, ifname) and the MTU for
        # the combo of (datacenter, peerHostname, peerIfname) and then
        # pare down the result to the rows where the two MTUs don't match
        query_df = (
            pd.merge(
                lldp_df,
                if_df[["datacenter", "hostname", "ifname", "mtu"]],
                on=["datacenter", "hostname", "ifname"],
                how="outer",
            )
            .dropna(how="any")
            .merge(
                if_df[["datacenter", "hostname", "ifname", "mtu"]],
                left_on=["datacenter", "peerHostname", "peerIfname"],
                right_on=["datacenter", "hostname", "ifname"],
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
