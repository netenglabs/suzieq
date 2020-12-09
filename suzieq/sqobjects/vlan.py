from suzieq.sqobjects.basicobj import SqObject


class VlanObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='vlan', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'vlan',
                                'state', 'vlanName', 'query_str']
        self._valid_arg_vals = {'state': ['active', 'suspended', '']}
