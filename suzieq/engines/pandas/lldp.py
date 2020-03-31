from .engineobj import SqEngineObject


class LldpObj(SqEngineObject):
    pass

    def summarize(self, **kwargs):
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        missing_mgmt = self.summary_df.query("mgmtIP == '-' or mgmtIP == ''") \
           .groupby(by=['namespace'])['mgmtIP'].count()

        self._add_field_to_summary('description', 'nunique')
        self._add_field_to_summary('hostname', 'count', 'rows')
        for field in ['hostname', 'peerHostname', 'mgmtIP']:
            self._add_list_or_count_to_summary(field)
        for i in self.ns.keys():
            self.ns[i].update({'missingMgmtIP': missing_mgmt.get(i,0)})

        self.summary_row_order = ['hostname', 'rows', 'description',
                                  'peerHostname', 'mgmtIP', 'missingMgmtIP']

        self._post_summarize()
        return self.ns_df.convert_dtypes()