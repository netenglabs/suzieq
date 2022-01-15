from suzieq.sqobjects.basicobj import SqObject


class VlanObj(SqObject):
    '''The object providing access to the vlany table'''

    def __init__(self, **kwargs):
        super().__init__(table='vlan', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'vlan',
                                'state', 'vlanName', 'query_str']
        self._valid_arg_vals = {'state': ['active', 'suspended', '']}
        self._unique_def_column = ['vlan']
