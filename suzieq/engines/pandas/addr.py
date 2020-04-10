import pandas as pd

from .engineobj import SqEngineObject


class AddrObj(SqEngineObject):

    def _get_cols(self, columns):
        """Get columns to fetch based on columns specified.
        Address is not a real table and so we need to craft what we expose
        """

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the dataframe that matches a given IPv4/v6/MAC address"""

        addr = kwargs.pop("address", None)

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

        # We have an extra var called getcols to avoid polluting the original
        columns = kwargs.pop("columns", ['default'])
        if columns == ['*']:
            getcols = self.iobj._allcols
        elif columns != ["default"]:
            if addrcol not in columns:
                getcols = columns + [addrcol]
        else:
            getcols = self.iobj._basiccols
            getcols.insert(-1, addrcol)

        df = self.get_valid_df("interfaces", sort_fields, columns=getcols,
                               **kwargs)

        if df.empty:
            return df

        # Works with pandas 0.25.0 onwards
        if addr:
            df = df.explode(addrcol).dropna(how='any')
            if '/' in addr:
                return df[df[addrcol].str.startswith(addr)]
            else:
                return df[df[addrcol].str.startswith(addr+'/')]
        else:
            return df[df[addrcol].apply(lambda x: len(x) != 0)]

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
