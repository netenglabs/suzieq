from typing import List
from ipaddress import ip_address, ip_network
from collections import defaultdict

import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class RoutesObj(SqPandasEngine):
    '''Backend class to handle manipulating routes table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'routes'

    def _cons_addnl_fields(self, columns: List[str], addnl_fields: List[str],
                           add_prefixlen: bool) -> List[str]:
        '''get all the additional columns we need'''

        if columns == ['default']:
            # Thanks to Linux, we need metric and weed out some routes
            addnl_fields.append('metric')
        elif columns != ['*']:
            for col in ['metric', 'ipvers', 'protocol', 'prefix']:
                if col not in columns:
                    addnl_fields.append(col)

        if add_prefixlen:
            if columns != ['*'] and all('prefixlen' not in x
                                        for x in [columns, addnl_fields]):
                addnl_fields.append('prefixlen')

        return addnl_fields

    def get(self, **kwargs):
        '''Return the routes table for the given filters'''

        prefixlen = kwargs.pop('prefixlen', '')
        prefix = kwargs.pop('prefix', [])
        ipvers = kwargs.pop('ipvers', '')
        user_query = kwargs.pop('query_str', '')

        columns = kwargs.pop('columns', ['default'])
        fields = self.schema.get_display_fields(columns)

        addnl_fields = []
        addnl_fields = self._cons_addnl_fields(
            columns, addnl_fields, prefixlen != '')

        self._add_active_to_fields(kwargs.get('view', self.iobj.view), fields,
                                   addnl_fields)

        # /32 routes are stored with the /32 prefix, so if user doesn't specify
        # prefix as some folks do, assume /32
        newpfx = []
        for item in prefix:
            ipvers = self._get_ipvers(item)

            if item and '/' not in item:
                if ipvers == 4:
                    item += '/32'
                else:
                    item += '/128'

            newpfx.append(item)

        user_query_cols = self._get_user_query_cols(user_query)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        df = super().get(addnl_fields=addnl_fields, prefix=newpfx,
                         ipvers=ipvers, columns=fields, **kwargs)

        if df.empty:
            return df

        if 'prefix' in df.columns:
            df = df.loc[df['prefix'] != "127.0.0.0/8"]
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)

            if (prefixlen or (columns == ['*']) or
                    any('prefixlen' in x for x in [columns, addnl_fields])):
                # This convoluted logic to handle the issue of invalid entries
                # for prefix in JUNOS routing table
                df['prefixlen'] = df['prefix'].str.split('/')
                df = df[df.prefixlen.str.len() == 2]
                df['prefixlen'] = df['prefixlen'].str[1].astype('int')

            if prefixlen:
                if any(map(prefixlen.startswith, ['<', '>'])):
                    query_str = f'prefixlen {prefixlen}'
                elif prefixlen.startswith('!'):
                    query_str = f'prefixlen != {prefixlen[1:]}'
                else:
                    query_str = f'prefixlen == {prefixlen}'

                # drop in reset_index to not add an additional index col
                df = df.query(query_str).reset_index(drop=True)

        if 'numNexthops' in columns or (columns == ['*']):
            srs_oif = df['oifs'].str.len()
            srs_hops = df['nexthopIps'].str.len()
            srs = np.array(list(zip(srs_oif, srs_hops)))
            srs_max = np.amax(srs, 1)
            df['numNexthops'] = srs_max

        if user_query:
            df = self._handle_user_query_str(df, user_query)

        return df.reset_index(drop=True)[fields]

    def summarize(self, **kwargs):
        '''Summarize routing table info'''

        self._init_summarize(**kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('uniquePrefixCnt', 'prefix', 'nunique'),
            ('uniqueVrfsCnt', 'vrf', 'nunique'),
        ]

        self._summarize_on_perdevice_stat = [
            ('routesPerHostStat', '', 'prefix', 'count')
        ]

        self._summarize_on_add_with_query = [
            ('ifRoutesCnt',
             'prefixlen == 30 or prefixlen == 31', 'prefix'),
            ('hostRoutesCnt', 'prefixlen == 32', 'prefix'),
            ('totalV4RoutesinNs', 'ipvers == 4', 'prefix'),
            ('totalV6RoutesinNs', 'ipvers == 6', 'prefix'),
        ]

        self._summarize_on_add_list_or_count = [
            ('routingProtocolCnt', 'protocol'),
            ('nexthopCnt', 'numNexthops'),
        ]

        self._gen_summarize_data()

        # Now for the stuff that is specific to routes
        routes_per_vrfns = self.summary_df.groupby(by=["namespace", "vrf"])[
            "prefix"].count().groupby("namespace")
        self._add_stats_to_summary(routes_per_vrfns, 'routesperVrfStat')
        self.summary_row_order.append('routesperVrfStat')

        device_with_defrt_per_vrfns = self.summary_df \
            .query('prefix == "0.0.0.0/0"') \
            .groupby(by=["namespace", "vrf"])[
                "hostname"].nunique()
        devices_per_vrfns = self.summary_df.groupby(by=["namespace", "vrf"])[
            "hostname"].nunique()

        # pylint: disable=expression-not-assigned
        {self.ns[i[0]].update({
            "deviceWithNoDefRoute":
            device_with_defrt_per_vrfns[i] == devices_per_vrfns[i]})
         for i in device_with_defrt_per_vrfns.keys() if i[0] in self.ns.keys()}
        self.summary_row_order.append('deviceWithNoDefRoute')

        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def lpm(self, **kwargs):
        '''Run longest prefix match on routing table for specified addr'''

        addr = kwargs.pop('address')
        kwargs.pop('ipvers', None)
        df = kwargs.pop('cached_df', pd.DataFrame())

        addnl_fields = []
        ipaddr = ip_address(addr)
        ipvers = ipaddr._version

        # User may specify a different set of columns than what we're after
        usercols = kwargs.pop('columns', ['default'])
        if usercols == ['default']:
            usercols = self.schema.get_display_fields(usercols)
            if 'timestamp' not in usercols:
                usercols.append('timestamp')
        else:
            usercols = self.schema.get_display_fields(usercols)
        cols = self.schema.get_display_fields(["default"])
        for col in usercols:
            if col not in cols:
                cols.append(col)

        addnl_fields = self._cons_addnl_fields(
            cols, addnl_fields, True)
        cols += addnl_fields
        rslt = pd.DataFrame()

        # if not using a pre-populated dataframe
        if df.empty:
            df = self.get(ipvers=ipvers, columns=cols, **kwargs)
        else:
            df = df.query(f'ipvers=={ipvers}')

        if df.empty:
            return df

        # Vectorized operation for faster results with IPv4:
        if ipvers == 4:
            intaddr = df.prefix.str.split('/').str[0] \
                .map(lambda y: int(''.join(['%02x' % int(x)
                                            for x in y.split('.')]),
                                   16))
            netmask = df.prefixlen \
                .map(lambda x: (0xffffffff << (32 - x)) & 0xffffffff)

            match = (ipaddr._ip & netmask) == (intaddr & netmask)
            rslt = df.loc[match.loc[match].index] \
                .sort_values('prefixlen', ascending=False) \
                .drop_duplicates(['namespace', 'hostname', 'vrf'])
        else:
            selected_entries = {}
            max_plens = defaultdict(int)
            for row in df.itertuples():
                rtentry = ip_network(row.prefix)
                if ipaddr in rtentry:
                    key = f'{row.namespace}-{row.hostname}-{row.vrf}'
                    if rtentry.prefixlen > max_plens[key]:
                        max_plens[key] = rtentry.prefixlen
                        selected_entries[key] = row
            if selected_entries:
                rslt = pd.DataFrame(list(selected_entries.values())) \
                    .drop(columns=['Index'], errors='ignore')
            else:
                rslt = pd.DataFrame()

        if rslt.empty:
            return rslt

        return rslt[usercols]
