#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import typing
import pandas as pd
from cyberpandas import to_ipnetwork, IPNetworkArray, IPNetworkType
from cyberpandas import IPNetAccessor

from .engineobj import SqEngineObject


class AddrObj(SqEngineObject):

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the dataframe that matches a given IP address"""

        addr = kwargs.get("address", None)
        if addr:
            del kwargs["address"]

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        if addr and "::" in addr:
            addrcol = "ip6AddressList"
        elif addr and ':' in addr:
            addrcol = "macaddr"
        else:
            addrcol = "ipAddressList"

        columns = kwargs.get("columns", [])
        if columns:
            del kwargs["columns"]
        else:
            columns = ['default']
        if columns != ["default"]:
            for col in addrcol:
                if col not in columns:
                    columns.insert(4, col)
        else:
            columns = ["datacenter", "hostname", "ifname", "state", addrcol,
                       "timestamp"]

        df = self.get_valid_df("interfaces", sort_fields, columns=columns,
                               **kwargs)

        # Works with pandas 0.25.0 onwards
        if addr and not df.empty:
            df = df.explode(addrcol).dropna(how='any')
            return df[df[addrcol].str.startswith(addr+'/')]
        else:
            return df[df[addrcol].apply(lambda x: len(x) != 0)]

    def summarize(self, **kwargs):
        """Describe the IP Address data"""

        addr = kwargs.get("address", None)
        if addr:
            del kwargs["address"]

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        columns = kwargs.get("columns", [])
        del kwargs["columns"]

        if columns == ["default"]:
            # We leave out IPv6 because link-local addresses pollute the info
            columns = ["datacenter", "hostname", "ifname", "ipAddressList",
                       "timestamp"]
            split_cols = ["ipAddressList"]
        else:
            split_cols = []
            for col in ["ipAddressList", "ip6AddressList"]:
                if col in columns:
                    split_cols.append(col)

        df = self.get_valid_df("interfaces", sort_fields, columns=columns,
                               **kwargs)
        if df.empty:
            return df

        for col in ["hostname", "ifname"]:
            if not kwargs.get(col, None):
                df.drop(columns=[col], inplace=True)
        newdf = self._split_dataframe_rows(df, split_cols)
        return newdf.describe(include="all").fillna("-")


if __name__ == "__main__":
    try:
        import fire

        fire.Fire(AddrObj)
    except ImportError:
        pass
        pass
