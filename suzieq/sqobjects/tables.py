import pandas as pd
from pandas.core.dtypes.dtypes import DatetimeTZDtype

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


class TablesObj(SqObject):
    '''The object providing access to the virtual table: tables'''

    def __init__(self, **kwargs) -> None:
        # We're passing any table name to get init to work
        super().__init__(table='tables', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']
        self._unique_def_column = ['table']

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'firstTime' in df.columns:
            if not isinstance(df.firstTime.dtype, DatetimeTZDtype):
                df['firstTime'] = humanize_timestamp(
                    df.firstTime.fillna(0),
                    self.cfg.get('analyzer', {}).get('timezone', None))

        if 'lastTime' in df.columns:
            if not isinstance(df.lastTime.dtype, DatetimeTZDtype):
                df['lastTime'] = humanize_timestamp(
                    df.lastTime.fillna(0),
                    self.cfg.get('analyzer', {}).get('timezone', None))

        return super().humanize_fields(df)
