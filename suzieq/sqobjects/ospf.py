from typing import List
import pandas as pd
from pandas.core.dtypes.dtypes import DatetimeTZDtype
import numpy as np

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


class OspfObj(SqObject):
    '''The object providing access to the ospf table'''

    def __init__(self, **kwargs):
        super().__init__(table='ospf', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'area',
                                'vrf', 'ifname', 'state', 'query_str']
        self._valid_assert_args = self._valid_get_args + ['result']
        self._valid_arg_vals = {
            'state': ['full', 'other', 'passive', '!full', '!passive',
                      '!other', ''],
            'result': ['all', 'pass', 'fail'],
        }

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'lastChangeTime' in df.columns:
            if not isinstance(df.lastChangeTime.dtype, DatetimeTZDtype):
                df['lastChangeTime'] = humanize_timestamp(
                    df.lastChangeTime.fillna(0),
                    self.cfg.get('analyzer', {}).get('timezone', None))

            if 'adjState' in df.columns:
                df['lastChangeTime'] = np.where(df.adjState == "passive",
                                                pd.Timestamp(0),
                                                df.lastChangeTime)

        return super().humanize_fields(df)

    def aver(self, **kwargs) -> pd.DataFrame:

        if kwargs.get('state', ''):
            raise ValueError('Cannot specify state with OSPF assert')

        return super().aver(**kwargs)

    def _get_empty_cols(self, columns: List[str], fun: str, **kwargs) \
            -> List[str]:
        if fun == 'assert' and columns in [['default'], ['*']]:
            return ['namespace', 'hostname', 'vrf', 'ifname',
                    'adjState', 'assertReason', 'result']
        return super()._get_empty_cols(columns, fun, **kwargs)
