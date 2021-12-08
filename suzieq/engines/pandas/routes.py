from collections import defaultdict
from .engineobj import SqPandasEngine
import pandas as pd
import numpy as np
from typing import Tuple
from ipaddress import ip_address, ip_network


class RoutesObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'routes'

    def _cons_addnl_fields(self, columns: list,
                           addnl_fields: list) -> Tuple[list, list]:
        '''get all the additional columns we need'''

        drop_cols = []

        if columns == ['default']:
            addnl_fields.append('metric')
            drop_cols += ['metric']
        elif columns != ['*'] and 'metric' not in columns:
            addnl_fields.append('metric')
            drop_cols += ['metric']

            if 'ipvers' not in columns:
                addnl_fields.append('ipvers')
                drop_cols += ['ipvers']

        return addnl_fields, drop_cols

    def get(self, **kwargs):
        def get_if_df_filtered(df: pd.DataFrame, ip_list: list, ip_vers: int) \
                -> pd.DataFrame:
            if ip_vers == 4:
                vers_to_drop = "ip6AddressList"
                vers_to_search = "ipAddressList"
            else:
                vers_to_drop = "ipAddressList"
                vers_to_search = "ip6AddressList"

            if_df = df.drop(columns=[vers_to_drop, "timestamp"]) \
                .explode(vers_to_search) \
                .fillna({vers_to_search: ''}) \
                .drop_duplicates() \
                .reset_index(drop=True)
            if_df[vers_to_search] = if_df[vers_to_search].apply(
                lambda x: x.split("/")[0])
            return if_df.loc[if_df[vers_to_search].isin(ip_list)] \
                .drop(columns=vers_to_search).reset_index(drop=True)

        prefixlen = kwargs.pop('prefixlen', '')
        prefix = kwargs.pop('prefix', [])
        ipvers = kwargs.pop('ipvers', '')
        addnl_fields = kwargs.pop('addnl_fields', [])
        user_query = kwargs.pop('query_str', '')
        origin = kwargs.pop('origin', '')

        columns = kwargs.get('columns', ['default'])
        addnl_fields, drop_cols = self._cons_addnl_fields(
            columns, addnl_fields)

        if origin:
            # retrieve all routes originated from ip addresses in field
            # "origin"
            df = super().get(addnl_fields=addnl_fields,
                             ipvers=ipvers, **kwargs)

            ipv4_list = [o for o in origin if self._get_ipvers(o) == 4]
            ipv6_list = [o for o in origin if self._get_ipvers(o) == 6]

            if_df = self._get_table_sqobj('interfaces').get(
                columns=['namespace', 'hostname',
                         'ipAddressList', 'ip6AddressList']
            )

            if4_df = get_if_df_filtered(if_df, ipv4_list, 4)
            if6_df = get_if_df_filtered(if_df, ipv6_list, 6)

            filtered_ifs_df = if4_df.merge(
                if6_df, on=["hostname", "namespace"], how='outer')

            # Select only pairs <namespace, hostname> which are present inside
            # 'bpg' and/or 'ospf' tables

            bgp_df = self._get_table_sqobj('bgp').get(
                columns=['namespace', 'hostname']
            ).drop(columns="timestamp").drop_duplicates() \
                .reset_index(drop=True)

            ospf_df = self._get_table_sqobj('ospf').get(
                columns=['namespace', 'hostname']
            ).drop_duplicates().reset_index(drop=True)

            bgp_df = bgp_df.merge(
                filtered_ifs_df[["hostname", "namespace"]],
                on=["hostname", "namespace"], how='right')

            ospf_df = ospf_df.merge(
                filtered_ifs_df[["hostname", "namespace"]],
                on=["hostname", "namespace"], how='right')

            filter_df = bgp_df.merge(
                ospf_df, on=["hostname", "namespace"],
                how='outer'
            )

            df = df.merge(filter_df, on=[
                "hostname", "namespace"], how="right")
        else:
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

        if user_query:
            df = df.query(user_query).reset_index(drop=True)
        if drop_cols:
            df.drop(columns=drop_cols, inplace=True, errors='ignore')

        return df

    def summarize(self, **kwargs):

        self._init_summarize(self.iobj._table, **kwargs)
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

        {self.ns[i[0]].update({
            "deviceWithNoDefRoute":
            device_with_defrt_per_vrfns[i] == devices_per_vrfns[i]})
         for i in device_with_defrt_per_vrfns.keys() if i[0] in self.ns.keys()}
        self.summary_row_order.append('deviceWithNoDefRoute')

        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def lpm(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        addr = kwargs.pop('address')
        kwargs.pop('ipvers', None)
        df = kwargs.pop('cached_df', pd.DataFrame())
        addnl_fields = kwargs.pop('addnl_fields', [])

        try:
            ipaddr = ip_address(addr)
            ipvers = ipaddr._version
        except ValueError as e:
            raise ValueError(e)

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

    def aver(self, **kwargs) -> pd.DataFrame:
        """Verify that the routing table is consistent
        The only check for now is to ensure every host has a default route/vrf'
        """
        df = self.get(**kwargs)
        if df.empty:
            return df
