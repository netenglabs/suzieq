from suzieq.sqobjects.basicobj import SqObject


class SqPollerObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='sqPoller', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'service',
                                'status', 'query_str']
        self._valid_arg_vals = {
            'status': ['all', 'pass', 'fail'],
        }
