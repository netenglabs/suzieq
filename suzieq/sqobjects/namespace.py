import pandas as pd

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


class NamespaceObj(SqObject):
    '''The object providing access to the virtual table: namespace'''

    def __init__(self, **kwargs):
        super().__init__(table='namespace', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'version', 'os',
                                'model', 'vendor', 'columns', 'query_str']
        self._unique_def_column = ['namespace']

    def get(self, **kwargs) -> pd.DataFrame:
        view = kwargs.get('view', self.view)
        if view == 'all':
            raise AttributeError("Cannot use 'view=all' with this table")
        return super().get(**kwargs)

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp fields'''
        if df.empty:
            return df

        if 'lastUpdate' in df.columns:
            df['lastUpdate'] = humanize_timestamp(df.lastUpdate,
                                                  self.cfg.get('analyzer', {})
                                                  .get('timezone', None))

        return super().humanize_fields(df)
