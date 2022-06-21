import pandas as pd
from pandas.core.dtypes.dtypes import DatetimeTZDtype

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


class DeviceObj(SqObject):
    '''The object providing access to the device table'''

    def __init__(self, **kwargs):
        super().__init__(table='device', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'os',
                                'vendor', 'model', 'status', 'version',
                                'query_str', 'ignore_neverpoll']
        self._valid_arg_vals = {
            'status': ['alive', 'dead', 'neverpoll',
                       '!alive', '!dead', '!neverpoll']
        }
        self._unique_def_column = ['model']

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        # Convert the bootup timestamp into a time delta
        if 'bootupTimestamp' in df.columns:
            if not isinstance(df.bootupTimestamp.dtype, DatetimeTZDtype):
                df['bootupTimestamp'] = humanize_timestamp(
                    df['bootupTimestamp']*1000,
                    self.cfg.get('analyzer', {}).get('timezone', None))

        return super().humanize_fields(df)
