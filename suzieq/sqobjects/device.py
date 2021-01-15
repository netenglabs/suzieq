from suzieq.sqobjects.basicobj import SqObject
import pandas as pd
from suzieq.utils import humanize_timestamp


class DeviceObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='device', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']

    def humanize_fields(self, df: pd.DataFrame, subset=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        # Convert the bootup timestamp into a time delta
        if 'bootupTimestamp' in df.columns:
            df['bootupTimestamp'] = humanize_timestamp(
                df['bootupTimestamp']*1000,
                self.cfg.get('analyzer', {}).get('timezone', None))

            uptime_cols = (df['timestamp'] - df['bootupTimestamp'])
            uptime_cols = pd.to_timedelta(uptime_cols, unit='s')
            df.insert(len(df.columns)-1, 'uptime', uptime_cols)

        return df
