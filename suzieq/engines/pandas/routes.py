#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

from .engineobj import SqEngineObject
from cyberpandas import to_ipnetwork, IPNetworkArray, IPNetworkType
from cyberpandas import IPNetAccessor


class RoutesObj(SqEngineObject):

    def get(self, **kwargs):

        df = super().get(**kwargs).query('prefix != ""')
        if not df.empty:
            df['prefix'].replace('default', '0.0.0.0/0', inplace=True)
            df['prefix'] = df['prefix'].astype('ipnetwork')

        return df

    def summarize(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs) \
                 .query('prefix != ""')

        if df.empty:
            return df

        df['prefix'].replace('default', '0.0.0.0/0', inplace=True)
        df['prefix'] = df.prefix.astype('ipnetwork')

        if kwargs.get("groupby"):
            return df.groupby(kwargs["groupby"]) \
                     .agg(lambda x: x.unique().tolist())
        else:
            for i in self.iobj._cat_fields:
                if (kwargs.get(i, []) or
                        "default" in kwargs.get("columns", [])):
                    df[i] = df[i].astype("category", copy=False)
            return df.describe(include="all").fillna("-")

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

        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs) \
                 .query('prefix != ""')

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
            return(pd.DataFrame(columns=cols))

        return idx.merge(df)
