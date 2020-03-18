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

        if 'prefix' in df.columns:
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)
            df['prefix'] = df.prefix.astype('ipnetwork')

        if kwargs.get("groupby"):
            return df.query('prefix != ""') \
                     .groupby(kwargs["groupby"]) \
                     .agg(lambda x: x.unique().tolist())
        else:
            for i in self.iobj._cat_fields:
                if (kwargs.get(i, []) or
                        "default" in kwargs.get("columns", [])):
                    df[i] = df[i].astype("category", copy=False)
            if 'prefix' in df.columns:
                return df.query('prefix != ""') \
                         .describe(include="all") \
                         .fillna("-")
            else:
                return df.describe(include="all") \
                         .fillna("-")

    def lpm(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        ipaddr = kwargs.get('address')
        del kwargs['address']

        cols = kwargs.get("columns", ["datacenter", "hostname", "vrf",
                                      "prefix", "nexthopIps", "oifs",
                                      "protocol"])

        if cols != ['default'] and 'prefix' not in cols:
            cols.insert(-1, 'prefix')

        # We indulge in a little hackery here by not filtering by hostname
        # at this point. For some inexplicable reason, the max() option
        # fails when the hostname is specified. So, we add the hostname filter
        # back later when returning the result
        hostname = kwargs.pop("hostname", [])
        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs) \
                 .query('prefix != ""')

        kwargs["hostname"] = hostname
        if df.empty:
            return df

        df['prefix'] = df.prefix.astype('ipnetwork')

        idx = df[['datacenter', 'hostname', 'vrf', 'prefix']] \
            .query("prefix.ipnet.supernet_of('{}')".format(ipaddr)) \
            .groupby(by=['datacenter', 'hostname', 'vrf']) \
            .max() \
            .dropna() \
            .reset_index()

        if idx.empty:
            return pd.DataFrame(columns=cols)

        if hostname:
            return idx.merge(df).query("hostname in @hostname")
        else:
            return idx.merge(df)
