from collections import defaultdict
from suzieq.engines.pandas.engineobj import SqEngineObject
import pandas as pd
from ipaddress import ip_address, ip_network


class RoutesObj(SqEngineObject):

    def get(self, **kwargs):

        prefixlen = kwargs.pop('prefixlen', None)
        columns = kwargs.get('columns', ['default'])
        df = super().get(**kwargs)
        if not df.empty and 'prefix' in df.columns:
            df = df.loc[df['prefix'] != "127.0.0.0/8"]
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)

            if prefixlen or ('prefixlen' in columns or columns == ['*']):
                df['prefixlen'] = df['prefix'].str.split(
                    '/').str[1].astype('int')

            if prefixlen:
                if any(map(prefixlen.startswith, ['<', '>'])):
                    query_str = f'prefixlen {prefixlen}'
                elif prefixlen.startswith('!'):
                    query_str = f'prefixlen != {prefixlen[1:]}'
                else:
                    query_str = f'prefixlen == {prefixlen}'
                df = df.query(query_str).reset_index()

            if columns != ['*'] and 'prefixlen' not in columns:
                df.drop(columns=['prefixlen'], inplace=True, errors='ignore')
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
            ('routingProtocolCnt', 'protocol')
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

        try:
            ipaddr = ip_address(addr)
            ipvers = ipaddr._version
        except ValueError as e:
            raise ValueError(e)

        cols = kwargs.pop("columns", ["namespace", "hostname", "vrf",
                                      "prefix", "prefixlen", "nexthopIps",
                                      "oifs", "protocol", "ipvers"])

        if cols != ['default']:
            if 'prefix' not in cols:
                cols.insert(-1, 'prefix')
            if 'ipvers' not in cols:
                cols.insert(-1, 'ipvers')
            if 'prefixlen' not in cols:
                cols.insert(-1, 'prefixlen')

        rslt = pd.DataFrame(cols)

        df = self.get(ipvers=str(ipvers), columns=cols, **kwargs)

        if df.empty:
            return df

        if 'prefixlen' not in df.columns and 'prefix' in df.columns:
            df['prefixlen'] = df['prefix'].str.split('/').str[1].astype('int')

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
                rslt = pd.DataFrame(list(selected_entries.values()))
            else:
                rslt = pd.DataFrame(cols)

        if 'prefixlen' not in cols:
            return rslt.drop(columns=['prefixlen'], errors='ignore')
        else:
            return rslt

    def aver(self, **kwargs) -> pd.DataFrame:
        """Verify that the routing table is consistent
        The only check for now is to ensure every host has a default route/vrf'
        """
        df = self.get(**kwargs)
        if df.empty:
            return df

    def unique(self, **kwargs) -> pd.DataFrame:
        """Return the unique elements as per user specification"""
        groupby = kwargs.pop("groupby", None)

        columns = kwargs.pop("columns", None)
        if columns is None or columns == ['default']:
            raise ValueError('Must specify columns with unique')

        if len(columns) > 1:
            raise ValueError('Specify a single column with unique')

        if groupby:
            getcols = columns + groupby.split()
        else:
            getcols = columns

        column = columns[0]

        type = kwargs.pop('type', 'entry')

        df = self.get_valid_df(self.iobj._table, self.iobj._sort_fields,
                               columns=getcols, **kwargs)
        if df.empty:
            return df

        if groupby:
            if type == 'host' and 'hostname' not in groupby:
                grp = df.groupby(by=groupby.split() + ['hostname', column])
                grpkeys = list(grp.groups.keys())
                gdict = {}
                for i, g in enumerate(groupby.split() + ['hostname', column]):
                    gdict[g] = [x[i] for x in grpkeys]
                r = pd.DataFrame(gdict).groupby(by=groupby.split())[column] \
                                       .value_counts()
                return (pd.DataFrame({'count': r})
                          .reset_index())

            else:
                r = df.groupby(by=groupby.split())[column].value_counts()
                return pd.DataFrame({'count': r}).reset_index()
        else:
            if type == 'host' and column != 'hostname':
                r = df.groupby('hostname').first()[column].value_counts()
            else:
                r = df[column].value_counts()

            df = (pd.DataFrame({column: r})
                    .reset_index()
                    .sort_values('index')
                    .rename(columns={column: 'count',
                                     'index': column}))
            df = df[df['count'] != 0]
            return df
