import pandas as pd

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
            if addrcol not in columns:
                columns.insert(-1, addrcol)
        else:
            columns = ["namespace", "hostname", "ifname", "state", addrcol,
                       "timestamp"]

        df = self.get_valid_df("interfaces", sort_fields, columns=columns,
                               **kwargs)

        if df.empty:
            return df

        # Works with pandas 0.25.0 onwards
        if addr:
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
            columns = ["namespace", "hostname", "ifname", "ipAddressList",
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

        if "ip6AddressList" in df.columns:
            newdf = df.explode("ipAddressList") \
                      .explode("ip6AddressList") \
                      .dropna(how='any')
        else:
            newdf = df.explode("ipAddressList") \
                      .dropna(how='any')

        return newdf.describe(include="all").fillna("-")
