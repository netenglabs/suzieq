from suzieq.sqobjects.basicobj import SqObject


class EvpnvniObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='evpnVni', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'vni',
                                'priVtepIp', 'query_str']
        self._valid_assert_args = ['namespace', 'hostname', 'status']
        self._valid_arg_vals = {
            'status': ['all', 'pass', 'fail'],
        }
