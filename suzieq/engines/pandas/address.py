import pandas as pd
from ipaddress import ip_interface

from .engineobj import SqPandasEngine
from suzieq.utils import build_query_str


class AddressObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'address'

    def addr_type(self, addr: list) -> list:

        rslt = []
        for a in addr:
            if ':' in a and '::' not in a:
                rslt.append(0)
            else:
                ipa = ip_interface(a)
                rslt.append(ipa._version)
        return rslt

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the dataframe that matches a given IPv4/v6/MAC address"""

        addr = kwargs.pop("address", [])
        columns = kwargs.get("columns", [])
        ipvers = kwargs.pop("ipvers", "")
        user_query = kwargs.pop('query_str', '')
        if user_query:
            if user_query.startswith('"') and user_query.endswith('"'):
                user_query = user_query[1:-1]

        vrf = kwargs.pop("vrf", "")
        addnl_fields = ['master']
        drop_cols = []

        v4addr = []
        v6addr = []
        macaddr = []
        try:
            addr_types = self.addr_type(addr)
        except ValueError:
            return pd.DataFrame({'error': ['Invalid address specified']})

        if columns != ['default'] and columns != ['*']:
            if ((4 in addr_types or ipvers == "v4") and
                    'ipAddressList' not in columns):
                addnl_fields.append('ipAddressList')
                drop_cols.append('ipAddressList')
            if ((6 in addr_types or ipvers == 'v6') and
                    'ip6AddressList' not in columns):
                addnl_fields.append('ip6AddressList')
                drop_cols.append('ip6AddressList')
            if ((0 in addr_types or ipvers == "l2") and
                    'macaddr' not in columns):
                addnl_fields.append('macaddr')
                drop_cols.append('macaddr')

        for i, a in enumerate(addr):
            if addr_types[i] == 0:
                macaddr.append(a)
            elif addr_types[i] == 4:
                if '/' not in a:
                    a += '/'
                v4addr.append(a)
            elif addr_types[i] == 6:
                if '/' not in a:
                    a += '/'
                v6addr.append(a)

        if vrf == "default":
            master = ''
        else:
            master = vrf
        df = self.get_valid_df("address", master=master,
                               addnl_fields=addnl_fields, **kwargs)

        if df.empty:
            return df

        if vrf == "default":
            df = df.query('master==""')

        if 4 in addr_types:
            df = df.explode('ipAddressList').fillna({'ipAddressList': ''})
        if 6 in addr_types:
            df = df.explode('ip6AddressList').fillna({'ip6AddressList': ''})

        query_str = ''
        prefix = ''
        # IMPORTANT: Don't mess with this order of query. Some bug in pandas
        # prevents it from working if macaddr isn't first and your query
        # contains both a macaddr and an IP address.
        if macaddr:
            query_str += f'{prefix} macaddr.isin({macaddr}) '
            prefix = 'or'
        if v4addr:
            for a in v4addr:
                query_str += f'{prefix} ipAddressList.str.startswith("{a}") '
                prefix = 'or'
        if v6addr:
            for a in v6addr:
                query_str += f'{prefix} ip6AddressList.str.startswith("{a}") '
                prefix = 'or'

        if not query_str:
            if ipvers == "v4":
                query_str = 'ipAddressList.str.len() != 0'
            elif ipvers == "v6":
                query_str = 'ip6AddressList.str.len() != 0'
            elif ipvers == "l2":
                query_str == 'macaddr.str.len() != 0'

        if query_str:
            df = df.query(query_str)

        df = self._handle_user_query_str(df, user_query)
        return df.drop(columns=drop_cols)

    def unique(self, **kwargs) -> pd.DataFrame:
        """Specific here only to rename vrf column to master"""
        column = kwargs.pop("columns", None)
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
                self.ns[i].update(
                    {'deviceWithv6AddressCnt': v6device.get(i, 0)})
                self.ns[i].update({'uniqueV6AddressCnt': v6addr.get(i, 0)})
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
                self.ns[i].update(
                    {'deviceWithv4AddressCnt': v4device.get(i, 0)})
                self.ns[i].update({'uniqueV4AddressCnt': v4addr.get(i, 0)})

            v4df['prefixlen'] = v4df.ipAddressList.str.split('/').str[1]

            # this doesn't work if we've filtered by namespace
            #  pandas complains about an index problem
            #  so instead we have the more complicated expression below
            #  they are equivalent
            # v4pfx = v4df.groupby(by=['namespace'])['prefixlen'] \
            #             .value_counts().rename('count').reset_index()
            v4pfx = v4df.groupby(by=['namespace', 'prefixlen'],
                                 as_index=False)['ipAddressList'].count() \
                .dropna()
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
                self.ns[i].update({'uniqueV4AddressCnt': 0})
                self.ns[i].update({'subnetsUsed': []})
                self.ns[i].update({'subnetTopCounts': []})

        self.summary_row_order = ['deviceCnt', 'addressCnt',
                                  'uniqueV4AddressCnt', 'uniqueV6AddressCnt',
                                  'uniqueIfMacCnt',
                                  'deviceWithv4AddressCnt',
                                  'deviceWithv6AddressCnt', 'subnetsUsed',
                                  'subnetTopCounts']
        self._post_summarize(check_empty_col='addressCnt')
        return self.ns_df.convert_dtypes()
