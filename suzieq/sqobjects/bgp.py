from typing import List
import pandas as pd
from pandas.core.dtypes.dtypes import DatetimeTZDtype

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


class BgpObj(SqObject):
    '''The object providing access to the bgp table'''

    def __init__(self, **kwargs):
        super().__init__(table='bgp', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'state',
                                'vrf', 'peer', 'asn', 'afiSafi', 'query_str']
        self._valid_arg_vals = {
            'state': ['Established', 'NotEstd', 'dynamic', ''],
            'result': ['all', 'pass', 'fail'],
        }
        self._valid_assert_args = self._valid_get_args + ['result']

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'estdTime' in df.columns:
            if not isinstance(df.estdTime.dtype, DatetimeTZDtype):
                df['estdTime'] = humanize_timestamp(
                    df.estdTime, self.cfg.get('analyzer', {})
                    .get('timezone', None))

        return super().humanize_fields(df)

    def _get_empty_cols(self, columns: List[str], fun: str, **kwargs) \
            -> List[str]:
        if fun == 'assert' and columns in [['default'], ['*']]:
            return ['namespace', 'hostname', 'vrf', 'peer',
                    'asn', 'peerAsn', 'state', 'peerHostname',
                    'result', 'assertReason', 'timestamp']
        return super()._get_empty_cols(columns, fun, **kwargs)
