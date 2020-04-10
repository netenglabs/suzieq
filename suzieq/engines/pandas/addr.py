import pandas as pd

from .engineobj import SqEngineObject


class AddrObj(SqEngineObject):

    def _get_addr_col(self, addr: str, ipvers: str, columns: str) -> str:
        """Get the address column to fetch based on columns specified.
        Address is not a real table and so we need to craft what we expose
        """

        addrcol = 'ipAddressList'
        if addr and "::" in addr:
            addrcol = "ip6AddressList"
        elif addr and ':' in addr:
            addrcol = "macaddr"
        elif addr:
            addrcol = "ipAddressList"
        else:
            addrcol = ("ipAddressList" if ipvers == "v4"
                       else "ip6AddressList" if ipvers == "v6" else "macaddr")
        return addrcol

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the dataframe that matches a given IPv4/v6/MAC address"""

        addr = kwargs.pop("address", None)
        columns = kwargs.get("columns", [])
        ipvers = kwargs.pop("ipvers", "4")

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        addrcol = self._get_addr_col(addr, ipvers, columns)
        df = self.get_valid_df("address", sort_fields, **kwargs)

        if df.empty:
            return df

        # Works with pandas 0.25.0 onwards
        if addr:
            df = df.explode(addrcol).dropna(how='any')
            if '/' in addr:
                return df[df[addrcol].str.startswith(addr)]
            else:
                return df[df[addrcol].str.startswith(addr+'/')]
        elif addrcol in df.columns:
            return df[df[addrcol].str.len() != 0]
        else:
            return df

    def summarize(self, **kwargs):
        """Describe the IP Address data"""

        addr = kwargs.pop("address", None)

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        df = self.get_valid_df("interfaces", sort_fields, **kwargs)
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
