from suzieq.sqobjects.basicobj import SqObject


class AddressObj(SqObject):

    def __init__(self, **kwargs):
        super().__init__(table='address', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'address',
                                'columns', 'ipvers', 'vrf', 'query_str']
