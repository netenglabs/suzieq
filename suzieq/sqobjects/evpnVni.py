from suzieq.sqobjects.basicobj import SqObject
import pandas as pd


class EvpnvniObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='evpnVni', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'vni',
                                'query_str']
        self._valid_assert_args = ['namespace', 'hostname', 'status']
        self._valid_arg_vals = {
            'status': ['all', 'pass', 'fail'],
        }

    def aver(self, **kwargs):
        """Assert that the BGP state is OK"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')
        try:
            self.validate_assert_input(**kwargs)
        except Exception as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        return self.engine.aver(**kwargs)
