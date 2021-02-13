import pandas as pd

from suzieq.sqobjects.basicobj import SqObject
from suzieq.utils import humanize_timestamp


class IfObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='interfaces', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'ifname', 'columns',
                                'state', 'type', 'mtu', 'query_str']
        self._valid_assert_args = ['namespace', 'hostname', 'ifname',
                                   'what', 'matchval', 'status']
        self._valid_arg_vals = {
            'state': ['up', 'down', ''],
            'status': ['all', 'pass', 'fail'],
        }

    def aver(self, what='mtu-match', **kwargs) -> pd.DataFrame:
        """Assert that interfaces are in good state"""
        try:
            self.validate_assert_input(**kwargs)
        except Exception as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        return self.engine.aver(what=what, **kwargs)

    def humanize_fields(self, df: pd.DataFrame, subset=None) -> pd.DataFrame:
        '''Humanize the timestamp and boot time fields'''
        if df.empty:
            return df

        if 'statusChangeTimestamp' in df.columns:
            df['statusChangeTimestamp'] = humanize_timestamp(
                df.statusChangeTimestamp,
                self.cfg.get('analyzer', {}).get('timezone', None))

        return df
