import pandas as pd

from suzieq.sqobjects.basicobj import SqObject


class IfObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='interfaces', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'ifname', 'columns',
                                'state', 'type', 'mtu']
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

        return self.engine_obj.aver(what=what, **kwargs)
