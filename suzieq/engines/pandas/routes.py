from suzieq.engines.pandas.engineobj import SqEngineObject
# this is needed for calling .astype('ipnetwork')
from cyberpandas import IPNetworkType
import pandas as pd


class RoutesObj(SqEngineObject):

    def get(self, **kwargs):

        prefixlen = kwargs.pop('prefixlen', None)
        df = super().get(**kwargs)
        if not df.empty and 'prefix' in df.columns:
            df = df.loc[df['prefix'] != "127.0.0.0/8"]
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)
            df['prefix'] = df['prefix'].astype('ipnetwork')

            if prefixlen:
                return df.query(f'prefix.ipnet.prefixlen {prefixlen}')

        return df

    def summarize(self, **kwargs):

        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('totalRoutesinNS', 'prefix', 'count'),
            ('uniquePrefixCnt', 'prefix', 'nunique'),
            ('uniqueVrfsCnt', 'vrf', 'nunique'),
        ]

        self._summarize_on_perhost_stat = [
            ('routesPerHostStat', '', 'prefix', 'count')
        ]

        self._summarize_on_add_with_query = [
            ('ifRoutesCnt',
             'prefix.ipnet.prefixlen == 30 or prefix.ipnet.prefixlen == 31',
             'prefix'),
            ('hostRoutesCnt', 'prefix.ipnet.prefixlen == 32', 'prefix'),
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

        hosts_with_defrt_per_vrfns = self.summary_df \
                                         .query("prefix.ipnet.is_default") \
                                         .groupby(by=["namespace", "vrf"])[
                                             "hostname"].nunique()
        hosts_per_vrfns = self.summary_df.groupby(by=["namespace", "vrf"])[
            "hostname"].nunique()

        {self.ns[i[0]].update({
            "hostsWithNoDefRoute":
            hosts_with_defrt_per_vrfns[i] == hosts_per_vrfns[i]})
         for i in hosts_with_defrt_per_vrfns.keys() if i[0] in self.ns.keys()}
        self.summary_row_order.append('hostsWithNoDefRoute')

        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def lpm(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        ipaddr = kwargs.get('address')
        del kwargs['address']

        cols = kwargs.get("columns", ["namespace", "hostname", "vrf",
                                      "prefix", "nexthopIps", "oifs",
                                      "protocol"])

        if cols != ['default'] and 'prefix' not in cols:
            cols.insert(-1, 'prefix')

        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs)

        if df.empty:
            return df

        df = df.query('prefix != ""')
        df['prefix'] = df.prefix.astype('ipnetwork')

        idx = df[['namespace', 'hostname', 'vrf', 'prefix']] \
            .query("prefix.ipnet.supernet_of('{}')".format(ipaddr)) \
            .groupby(by=['namespace', 'hostname', 'vrf'])['prefix'] \
            .max() \
            .dropna() \
            .reset_index()

        if idx.empty:
            return pd.DataFrame(columns=cols)

        return idx.merge(df)

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

            return (pd.DataFrame({column: r})
                    .reset_index()
                    .sort_values('index')
                    .rename(columns={column: 'count',
                                     'index': column}))
