import pandas as pd

from .engineobj import SqEngineObject


class AddressObj(SqEngineObject):

    def _get_addr_col(self, addr: str, ipvers: str, columns: str) -> str:
        """Get the address column to fetch based on columns specified.
        Address is not a real table and so we need to craft what we expose
        """

        addrcol = None
        if addr and "::" in addr:
            addrcol = "ip6AddressList"
        elif addr and ':' in addr:
            addrcol = "macaddr"
        elif addr:
            addrcol = "ipAddressList"
        elif ipvers == "v4":
            addrcol = "ipAddressList"
        elif ipvers == "v6":
            addrcol = "ip6AddressList"
        return addrcol

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the dataframe that matches a given IPv4/v6/MAC address"""

        addr = kwargs.pop("address", None)
        columns = kwargs.get("columns", [])
        ipvers = kwargs.pop("ipvers", "")
        vrf = kwargs.pop("vrf", "")
        addnl_fields = ['origIfname', 'master']

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        addrcol = self._get_addr_col(addr, ipvers, columns)
        df = self.get_valid_df("address", sort_fields, master=vrf,
                               addnl_fields=addnl_fields, **kwargs)

        if df.empty:
            return df

        df['ifname'] = df['origIfname']
        if not vrf and not any(i in columns for i in ["master", "vrf"]):
            df.drop(columns=['origIfname', 'master'], inplace=True)
        else:
            df.drop(columns=['origIfname'], inplace=True)

        if addr:
            addr = [x+'/' if '/' not in x else x for x in addr]
            pattern = '|'.join(addr)

        # Works with pandas 0.25.0 onwards
        if addr and addrcol == "macaddr":
            return df[df[addrcol] == addr]
        elif addr:
            df = df.explode(addrcol).dropna(how='any')
            return df[df[addrcol].str.contains(pattern)]
        elif addrcol in df.columns:
            return df[df[addrcol].str.len() != 0]
        else:
            return df

    def unique(self, **kwargs) -> pd.DataFrame:
        """Specific here only to rename vrf column to master"""
        column = kwargs.pop("columns", '')
        if column == ["vrf"]:
            column = ["master"]
        df = super().unique(columns=column, **kwargs)
        if not df.empty:
            if 'vrf' in column:
                return df.query("master != 'bridge'") \
                         .rename({'master': 'vrf'}, axis='columns') \
                         .replace({'vrf': {'': 'default'}})
        return df

    def summarize(self, **kwargs) -> pd.DataFrame:
        """Summarize address related info"""

        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._add_field_to_summary('hostname', 'nunique', 'deviceCnt')
        self._add_field_to_summary('hostname', 'count', 'addressCnt')
        self._add_field_to_summary('macaddr', 'nunique', 'uniqueIfMacCnt')

        v6df = self.summary_df.explode('ip6AddressList') \
            .dropna(how='any') \
            .query('~ip6AddressList.str.startswith("fe80")')
        if not v6df.empty:
            v6device = v6df.groupby(by=['namespace'])['hostname'].nunique()
            v6addr = v6df.groupby(by=['namespace'])['ip6AddressList'].nunique()
            for i in self.ns.keys():
                self.ns[i].update({'deviceWithv6AddressCnt': v6device[i]})
                self.ns[i].update({'uniqueV6AddressCnt': v6addr[i]})
        else:
            for i in self.ns.keys():
                self.ns[i].update({'deviceWithv6AddressCnt': 0})
                self.ns[i].update({'uniqueV6AddressCnt': 0})

        v4df = self.summary_df.explode('ipAddressList') \
            .dropna(how='any') \
            .query('ipAddressList.str.len() != 0')
        if not v4df.empty:
            v4device = v4df.groupby(by=['namespace'])['hostname'].nunique()
            v4addr = v4df.groupby(by=['namespace'])['ipAddressList'].nunique()
            for i in self.ns.keys():
                self.ns[i].update({'deviceWithv4AddressCnt': v4device[i]})
                self.ns[i].update({'uniqueV4AddressCnt': v4addr[i]})

            v4df['prefixlen'] = v4df.ipAddressList.str.split('/').str[1]

            # this doesn't work if we've filtered by namespace
            #  pandas complains about an index problem
            #  so instead we have the more complicated expression below
            #  they are equivalent
            # v4pfx = v4df.groupby(by=['namespace'])['prefixlen'] \
            #             .value_counts().rename('count').reset_index()
            v4pfx = v4df.groupby(by=['namespace', 'prefixlen'], as_index=False)[
                'ipAddressList'].count().dropna()
            v4pfx = v4pfx.rename(columns={'ipAddressList': 'count'})
            v4pfx['count'] = v4pfx['count'].astype(int)
            v4pfx = v4pfx.sort_values(by=['count'], ascending=False)

            for i in self.ns.keys():
                cnts = []
                v4pfx[v4pfx['namespace'] == i].apply(
                    lambda x: cnts.append(x['prefixlen']), axis=1, args=cnts)
                self.ns[i].update({'subnetsUsed': cnts})
                cnts = []
                v4pfx[v4pfx['namespace'] == i].apply(
                    lambda x: cnts.append({x['prefixlen']: x['count']}),
                    axis=1, args=cnts)
                self.ns[i].update({'subnetTopCounts': cnts[:3]})
        else:
            for i in self.ns.keys():
                self.ns[i].update({'deviceWithv4AddressCnt': 0})
                self.ns[i].update({'uniqueV6AddressCnt': 0})

        self.summary_row_order = ['deviceCnt', 'addressCnt',
                                  'uniqueV4AddressCnt', 'uniqueV6AddressCnt',
                                  'uniqueIfMacCnt',
                                  'deviceWithv4AddressCnt',
                                  'deviceWithv6AddressCnt', 'subnetsUsed',
                                  'subnetTopCounts']
        self._post_summarize(check_empty_col='addressCnt')
        return self.ns_df.convert_dtypes()
