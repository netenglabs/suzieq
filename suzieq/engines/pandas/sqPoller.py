from suzieq.engines.pandas.engineobj import SqEngineObject


class SqpollerObj(SqEngineObject):
    pass

    def summarize(self, **kwargs):
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._add_field_to_summary('hostname', 'count', 'rows')
        for field in ['hostname', 'service', 'emptyCount',
                      'status']:
            self._add_list_or_count_to_summary(field)
        for field in ['pollExcdPeriodCount', 'gatherTime', 'nodeQsize',
                      'svcQsize', 'totalTime', 'wrQsize']:
            self._add_stats_to_summary(self.nsgrp[field], field)

        self.summary_row_order = ['hostname', 'rows', 'service', 'status',
                                  'pollExcdPeriodCount', 'nodeQsize',
                                  'svcQsize', 'wrQsize', 'gatherTime',
                                  'totalTime', 'emptyCount']
        self._post_summarize()
        return self.ns_df.convert_dtypes()
