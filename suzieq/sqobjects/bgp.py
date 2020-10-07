from suzieq.sqobjects.basicobj import SqObject
import pandas as pd


class BgpObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='bgp', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'state',
                                'status', 'vrf', 'peer'] 
        self._valid_assert_args = ['namespace', 'hostname', 'start_time',
                                  'end_time', 'vrf', ]

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
