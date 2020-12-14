from suzieq.sqobjects.basicobj import SqObject
import pandas as pd
from suzieq.utils import humanize_timestamp


class BgpObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='bgp', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'state',
                                'vrf', 'peer', 'query_str']
        self._valid_arg_vals = {
            'state': ['Established', 'NotEstd', ''],
            'status': ['all', 'pass', 'fail'],
        }
        self._valid_assert_args = ['namespace', 'hostname', 'vrf', 'status']

    def aver(self, **kwargs):
        """Assert that the BGP state is OK"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')
        try:
            self.validate_assert_input(**kwargs)
        except Exception as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        return self.engine_obj.aver(**kwargs)

    def humanize_fields(self, df: pd.DataFrame, subset=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'estdTime' in df.columns:
            df['estdTime'] = humanize_timestamp(df.estdTime)

        return df
