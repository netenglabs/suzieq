from suzieq.engines.pandas.engineobj import SqPandasEngine


class DevconfigObj(SqPandasEngine):
    '''Backend class to handle manipulating device config table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'devconfig'

    def get(self, **kwargs):
        columns = kwargs.pop('columns', ['default'])
        user_query = kwargs.get('query_str', '')

        fields = self.schema.get_display_fields(columns)
        addnl_fields = self._get_user_query_cols(user_query)

        df = super().get(columns=fields, addnl_fields=addnl_fields, **kwargs)

        return df.reset_index(drop=True)[fields]
