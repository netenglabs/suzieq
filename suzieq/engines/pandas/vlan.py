#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import pandas as pd

from .engineobj import SQEngineObject


class vlanObj(SQEngineObject):

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the dataframe that matches a given VLANs"""

        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        # Our query string formatter doesn't understand handling queries
        # with lists yet. So, pull it out.
        vlan = kwargs.get('vlan', None)
        if vlan:
            del kwargs['vlan']
            vset = set([int(x) for x in vlan.split()])
        else:
            vset = None

        df = self.get_valid_df("vlan", sort_fields, **kwargs)

        # We're checking if any element of given list is in the vlan
        # column
        if vset:
            return (df[df.vlan.map(lambda x: not vset.isdisjoint(x))])
        else:
            return(df)

    def summarize(self, **kwargs):
        """Describe the IP Address data"""

        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        df = self.get_valid_df(self.iobj._table, sort_fields,
                               **kwargs)
        if not df.empty:
            # To summarize accurately, we need to explode the vlan
            # column from a list to an individual entry for each
            # vlan in that list. The resulting set can be huge if them
            # number of vlans times the ports is huge.
            #
            # the 'explode' only works post pandas 0.25
            df = df.explode('vlan').dropna(how='any')
            if kwargs.get("groupby"):
                return df.groupby(kwargs["groupby"]) \
                         .agg(lambda x: x.unique().tolist())
            else:
                for i in self.iobj._cat_fields:
                    if (kwargs.get(i, []) or
                            "default" in kwargs.get("columns", [])):
                        df[i] = df[i].astype("category", copy=False)
                return df.describe(include="all").fillna("-")

        return df

if __name__ == "__main__":
    pass
