from suzieq.engines.pandas.engineobj import SqPandasEngine


class MlagObj(SqPandasEngine):
    '''Backend class to handle manipulating MLAG table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'mlag'

    def get(self, **kwargs):
        columns = kwargs.pop('columns', ['default'])
        user_query = kwargs.get('query_str', '')

        fields = self.schema.get_display_fields(columns)
        addnl_fields = self._get_user_query_cols(user_query)

        df = super().get(columns=fields, addnl_fields=addnl_fields, **kwargs)

        return df.reset_index(drop=True)[fields]

    def summarize(self, **kwargs):
        """Summarize MLAG info"""

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('uniqueSystemIdCnt', 'systemId', 'nunique')
        ]

        self._summarize_on_add_with_query = [
            ('devicesWithfailedStateCnt', 'state != "active"', 'state'),
            ('devicesWithBackupInactiveCnt', 'state == "active"',
             'backupActive')
        ]

        self._summarize_on_add_stat = [
            ('mlagNumDualPortsStat', 'state == "active"', 'mlagDualPortsCnt'),
            ('mlagNumSinglePortStat', 'state == "active"',
             'mlagSinglePortsCnt'),
            ('mlagNumErrorPortStat', 'state == "active"', 'mlagErrorPortsCnt')
        ]

        return super().summarize(**kwargs)
