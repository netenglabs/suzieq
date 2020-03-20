from suzieq.engines.pandas.engineobj import SqEngineObject
# this is needed for calling .astype('ipnetwork')
from cyberpandas import IPNetworkType
import pandas as pd


class RoutesObj(SqEngineObject):

    def get(self, **kwargs):

        df = super().get(**kwargs)
        if not df.empty and 'prefix' in df.columns:
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)
            df['prefix'] = df['prefix'].astype('ipnetwork')
            return df.query('prefix != ""')

        return df

    def summarize(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs)

        if df.empty:
            return df

        # Filter out local loopback IP
        df = df[(df.prefix != '127.0.0.0/8')]
        if df.empty:
            return df

        if 'prefix' in df.columns:
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)
            df['prefix'] = df.prefix.astype('ipnetwork')

        # Routes DF has an interesting side-effect that I've to investigate.
        # The DF returned still has the namespaces filtered out, but they
        # show up when we do groupby. I don't know why. So we create the
        # data structure assuming all namespaces, and since they contain no
        # content, we'll eliminate them in the end
        nsgrp = df.groupby(by=["namespace"])
        ns = {i: {} for i in nsgrp.groups.keys()}

        hosts_per_ns = nsgrp["hostname"].nunique()
        {ns[i].update({'hosts': hosts_per_ns[i]}) for i in hosts_per_ns.keys()}

        vrfs = nsgrp["vrf"].nunique()
        {ns[i].update({'vrfs': vrfs[i]}) for i in vrfs.keys()}

        routes_per_ns = nsgrp["prefix"].count()
        {ns[i].update({'routes': routes_per_ns[i]})
         for i in routes_per_ns.keys()}

        unique_routes_per_ns = nsgrp["prefix"].nunique()
        {ns[i].update({'uniqueRoutes': unique_routes_per_ns[i]})
         for i in unique_routes_per_ns.keys()}

        rh_per_hns = df.groupby(by=["namespace", "hostname"])[
            "prefix"].count()
        med_rh_per_ns = rh_per_hns.groupby("namespace").median()
        {ns[i].update({'medianRoutesperHost': med_rh_per_ns[i]})
         for i in med_rh_per_ns.keys()}

        routes_per_vrfns = df.groupby(by=["namespace", "vrf"])[
            "prefix"].count().groupby("namespace").median()
        {ns[i].update({'medianRoutesperVrf': routes_per_vrfns[i]})
         for i in routes_per_vrfns.keys()}

        hr_per_ns = df.query("prefix.ipnet.prefixlen == 32") \
                      .groupby(by=['namespace'])['prefix'].count()
        {ns[i].update({'hostRoutes': hr_per_ns[i]}) for i in hr_per_ns.keys()}
        ifr_per_ns = df.query("prefix.ipnet.prefixlen == 30 or "
                              "prefix.ipnet.prefixlen == 31") \
                       .groupby(by=['namespace'])['prefix'].count()
        {ns[i].update({'interfaceRoutes': ifr_per_ns[i]})
         for i in ifr_per_ns.keys()}

        proto_per_ns = nsgrp["protocol"].unique()
        proto_per_ns.apply(lambda x: x.sort())
        {ns[i].update({'protocols': proto_per_ns[i]})
         for i in proto_per_ns.keys()}

        hosts_with_defrt_per_vrfns = df.query("prefix.ipnet.is_default") \
                                       .groupby(by=["namespace", "vrf"])[
                                           "hostname"].nunique()
        hosts_per_vrfns = df.groupby(by=["namespace", "vrf"])[
            "hostname"].nunique()
        {ns[i[0]].update({"hostsNoDefRoute":
                          hosts_with_defrt_per_vrfns[i] == hosts_per_vrfns[i]})
         for i in hosts_with_defrt_per_vrfns.keys()}

        # Eliminate all the fields without the desired namespace if provided
        # As described earlier this is only required for routes
        namespaces = set(tuple(kwargs.get("namespace", [])))
        if namespaces:
            nskeys = set(tuple(ns.keys()))
            deselect_keys = nskeys - namespaces
            if deselect_keys:
                for key in deselect_keys:
                    del ns[key]

        return(pd.DataFrame(ns).convert_dtypes())

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

        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs) \
                 .query('prefix != ""')

        if df.empty:
            return df

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
