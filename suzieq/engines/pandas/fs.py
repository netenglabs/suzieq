from suzieq.engines.pandas.engineobj import SqPandasEngine


class FsObj(SqPandasEngine):
    '''Backend class to handle manipulating filesystem table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'fs'

    def get(self, **kwargs):
        columns = kwargs.get('columns', ['default'])
        fields = self.schema.get_display_fields(columns)

        self._add_active_to_fields(
            kwargs.get('view', self.iobj.view), fields, [])

        df = super().get(**kwargs)

        if df.empty:
            return df

        return df[fields]
