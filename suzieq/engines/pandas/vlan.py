import pandas as pd

from .engineobj import SqEngineObject


class VlanObj(SqEngineObject):

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

        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._add_field_to_summary('hostname', 'count', 'rows')
        for field in ['pvid']:
            self._add_list_or_count_to_summary(field)

        # To summarize accurately, we need to explode the vlan
        # column from a list to an individual entry for each
        # vlan in that list. The resulting set can be huge if them
        # number of vlans times the ports is huge.
        #
        # the 'explode' only works post pandas 0.25

        self.summary_df = self.summary_df.explode('vlan').dropna(how='any')
        self.nsgrp = self.summary_df.groupby(by=["namespace"])

        if not self.summary_df.empty:
            for field in ['vlan']:
                self._add_list_or_count_to_summary(field)


        self._post_summarize()
        return self.ns_df.convert_dtypes()