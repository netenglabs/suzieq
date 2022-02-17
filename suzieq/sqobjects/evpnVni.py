from suzieq.sqobjects.basicobj import SqObject


class EvpnvniObj(SqObject):
    '''The object providing access to the evpnVni table'''

    def __init__(self, **kwargs):
        super().__init__(table='evpnVni', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'vni',
                                'priVtepIp', 'query_str']
        self._valid_assert_args = self._valid_get_args + ['result']
        self._valid_arg_vals = {
            'result': ['all', 'pass', 'fail'],
        }
