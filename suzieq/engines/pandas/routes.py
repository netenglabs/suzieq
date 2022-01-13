from typing import Tuple
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

    def _cons_addnl_fields(self, columns: list,
                           addnl_fields: list) -> Tuple[list, list]:
        '''get all the additional columns we need'''

        drop_cols = []

        if columns == ['default']:
            addnl_fields.append('metric')
            drop_cols.append('metric')
        elif columns != ['*'] and 'metric' not in columns:
            addnl_fields.append('metric')
            drop_cols += ['metric']

            if 'ipvers' not in columns:
                addnl_fields.append('ipvers')
                drop_cols += ['ipvers']

            if 'protocol' not in columns:
                addnl_fields.append('protocol')
                drop_cols.append('protocol')

        return addnl_fields, drop_cols

    def _fill_in_oifs(self, df: pd.DataFrame()):
        '''Some NOS do not return an ifname, we need to fix it'''

        def add_oifs(row, ifdict):
            if row.nexthopIps.size == 0:
                return row.oifs

            oifs = []
            for hop in row.nexthopIps:
                for k, v in ifdict.items():
                    if hop in [str(x) for x in ip_network(k).hosts()]:
                        oifs.append(v)
                        break
            return np.array(oifs)

        conn_if_dict = df \
            .query('protocol == "connected"')[['prefix', 'oifs']] \
            .to_dict(orient='records')

        conn_if_dict = {x['prefix']: x['oifs'][0] for x in conn_if_dict}
        work_df = df.query('oifs.str.len() == 0').reset_index(drop=True)
        if not work_df.empty:
            ok_df = df.query('oifs.str.len() != 0').reset_index(drop=True)
            work_df['oifs'] = work_df.apply(add_oifs, args=(conn_if_dict,),
                                            axis=1)
            df = pd.concat([ok_df, work_df]).reset_index(drop=True)

        return df

    def get(self, **kwargs):
        '''Return the routes table for the given filters'''

        prefixlen = kwargs.pop('prefixlen', '')
        prefix = kwargs.pop('prefix', [])
        ipvers = kwargs.pop('ipvers', '')
        addnl_fields = kwargs.pop('addnl_fields', [])
        user_query = kwargs.pop('query_str', '')

        columns = kwargs.get('columns', ['default'])
        addnl_fields, drop_cols = self._cons_addnl_fields(
            columns, addnl_fields)

        if prefixlen and ('prefixlen' not in columns or columns != ['*']):
            addnl_fields.append('prefixlen')
            drop_cols.append('prefixlen')

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

        df = super().get(addnl_fields=addnl_fields, prefix=newpfx,
                         ipvers=ipvers, **kwargs)

        if not df.empty and 'prefix' in df.columns:
            df = df.loc[df['prefix'] != "127.0.0.0/8"]
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)

            if prefixlen or 'prefixlen' in columns or (columns == ['*']):
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

            if columns != ['*'] and 'prefixlen' not in columns:
                drop_cols.append('prefixlen')

        if not df.empty and ('numNexthops' in columns or (columns == ['*'])):
            srs_oif = df['oifs'].str.len()
            srs_hops = df['nexthopIps'].str.len()
            srs = np.array(list(zip(srs_oif, srs_hops)))
            srs_max = np.amax(srs, 1)
            df.insert(len(df.columns)-1, 'numNexthops', srs_max)

        if not df.empty and 'oifs' in df.columns:
            df = self._fill_in_oifs(df)

        if user_query:
            df = self._handle_user_query_str(df, user_query)
        if drop_cols:
            df.drop(columns=drop_cols, inplace=True, errors='ignore')

        return df

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
        addnl_fields = kwargs.pop('addnl_fields', [])

        ipaddr = ip_address(addr)
        ipvers = ipaddr._version  # pylint: disable=protected-access

        usercols = kwargs.pop('columns', ['default'])
        if usercols == ['default']:
            usercols = self.schema.get_display_fields(usercols)
            if 'timestamp' not in usercols:
                usercols.append('timestamp')
        else:
            usercols = self.schema.get_display_fields(usercols)
        cols = ["default"]
        drop_cols = []

        addnl_fields, drop_cols = self._cons_addnl_fields(
            cols, addnl_fields)
        rslt = pd.DataFrame()

        # if not using a pre-populated dataframe
        if df.empty:
            df = self.get(ipvers=ipvers, columns=cols,
                          addnl_fields=addnl_fields, **kwargs)
        else:
            df = df.query(f'ipvers=={ipvers}')

        if df.empty:
            return df

        if 'prefixlen' not in df.columns:
            df['prefixlen'] = df['prefix'].str.split('/')
            df = df[df.prefixlen.str.len() == 2]
            df['prefixlen'] = df['prefixlen'].str[1].astype('int')
            drop_cols.append('prefixlen')

        # Vectorized operation for faster results with IPv4:
        if ipvers == 4:
            intaddr = df.prefix.str.split('/').str[0] \
                .map(lambda y: int(''.join(['%02x' % int(x)
                                            for x in y.split('.')]),
                                   16))
            netmask = df.prefixlen \
                .map(lambda x: (0xffffffff << (32 - x)) & 0xffffffff)
            # pylint: disable=protected-access
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

        return rslt[usercols]
