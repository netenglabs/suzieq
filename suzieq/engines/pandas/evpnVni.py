from .engineobj import SqEngineObject


class EvpnvniObj(SqEngineObject):
    pass


    def summarize(self, **kwargs):
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._add_field_to_summary('hostname', 'count', 'rows')
        for field in ['vni', 'type', 'vrf']:
            self._add_list_or_count_to_summary(field)

        self._add_stats_to_summary(self.nsgrp['numMacs'], 'numMacs')
        self._add_stats_to_summary(self.nsgrp['numArpNd'], 'numArpNd')

        # To summarize accurately, we need to explode the remoteVteps
        # column from a list to an individual entry for each
        # remoteVteps in that list. The resulting set can be huge if them
        # number of Vteps times the ports is huge.
        #
        # the 'explode' only works post pandas 0.25

        self.summary_df = self.summary_df.explode('remoteVteps').dropna(how='any')
        self.nsgrp = self.summary_df.groupby(by=["namespace"])

        if not self.summary_df.empty:
            for field in ['remoteVteps']:
                self._add_list_or_count_to_summary(field)


        self._post_summarize()
        return self.ns_df.convert_dtypes()