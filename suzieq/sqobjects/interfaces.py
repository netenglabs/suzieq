from typing import List
import pandas as pd
from pandas.core.dtypes.dtypes import DatetimeTZDtype

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


class InterfacesObj(SqObject):
    '''The object providing access to the interfaces table'''

    def __init__(self, **kwargs):
        super().__init__(table='interfaces', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'ifname', 'columns',
                                'state', 'type', 'mtu', 'master', 'ifindex',
                                'vrf', 'portmode', 'vlan', 'query_str']
        self._valid_assert_args = self._valid_get_args + \
            ['what', 'value', 'result', 'ignore_missing_peer']
        self._valid_arg_vals = {
            'state': ['up', 'down', 'notConnected', '!up', '!down',
                      '!notConnected', ''],
            'result': ['all', 'pass', 'fail'],
        }
        self._unique_def_column = ['type']

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'statusChangeTimestamp' in df.columns:
            if not isinstance(df.statusChangeTimestamp.dtype, DatetimeTZDtype):
                df['statusChangeTimestamp'] = humanize_timestamp(
                    df.statusChangeTimestamp,
                    self.cfg.get('analyzer', {}).get('timezone', None))

        return super().humanize_fields(df)

    def _get_empty_cols(self, columns: List[str], fun: str, **kwargs) \
            -> List[str]:
        if fun == 'assert':
            if columns in [['default'], ['*']]:
                if kwargs.get('what') == 'mtu-value':
                    return ["namespace", "hostname", "ifname", "state",
                            "mtu", "timestamp", "result"]
                else:
                    return ['namespace', 'hostname', 'ifname', 'state',
                            'peerHostname', 'peerIfname', 'result',
                            'assertReason', 'timestamp']
        return super()._get_empty_cols(columns, fun, **kwargs)
