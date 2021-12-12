import pandas as pd

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


class IfObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='interfaces', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'ifname', 'columns',
                                'state', 'type', 'mtu', 'master', 'ifindex',
                                'vrf', 'query_str']
        self._valid_assert_args = ['namespace', 'hostname', 'ifname', 'what',
                                   'matchval', 'status', 'ignore_missing_peer']
        self._valid_arg_vals = {
            'state': ['up', 'down', 'notConnected', '!up', '!down',
                      '!notConnected', ''],
            'status': ['all', 'pass', 'fail'],
        }
        self._unique_def_column = ['type']

    def humanize_fields(self, df: pd.DataFrame, subset=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'statusChangeTimestamp' in df.columns:
            df['statusChangeTimestamp'] = humanize_timestamp(
                df.statusChangeTimestamp,
                self.cfg.get('analyzer', {}).get('timezone', None))

        return super().humanize_fields(df)
