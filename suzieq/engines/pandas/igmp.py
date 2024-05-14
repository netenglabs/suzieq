from suzieq.engines.pandas.engineobj import SqPandasEngine


class IgmpObj(SqPandasEngine):
    '''Backend class to handle manipulating mroutes table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'igmp'

    def get(self, **kwargs):
        '''Return the igmp table for the given filters'''

        user_query = kwargs.pop('query_str', '')
        columns = kwargs.pop('columns', ['default'])
        fields = self.schema.get_display_fields(columns)

        df = super().get(columns=fields, **kwargs)

        if user_query:
            df = self._handle_user_query_str(df, user_query)

        return df[fields]

    def summarize(self, **kwargs):
        self._init_summarize(**kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._gen_summarize_data()

        groups_per_vrfns = self.summary_df.groupby(by=["namespace", "vrf"])[
            "group"].count().groupby("namespace")
        self._add_stats_to_summary(groups_per_vrfns, 'igmpGroupsPerVrfStat')

        self.summary_row_order.append('igmpGroupsPerVrfStat')

        self._post_summarize()
        return self.ns_df.convert_dtypes()
