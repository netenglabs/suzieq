from suzieq.sqobjects.basicobj import SqObject
import pandas as pd
from suzieq.utils import humanize_timestamp


class BgpObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='bgp', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'state',
                                'vrf', 'peer', 'asn', 'query_str']
        self._valid_arg_vals = {
            'state': ['Established', 'NotEstd', 'dynamic', ''],
            'status': ['all', 'pass', 'fail'],
        }
        self._valid_assert_args = ['namespace', 'hostname', 'vrf', 'status']

    def humanize_fields(self, df: pd.DataFrame, subset=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'estdTime' in df.columns:
            df['estdTime'] = humanize_timestamp(df.estdTime,
                                                self.cfg.get('analyzer', {})
                                                .get('timezone', None))

        return df
