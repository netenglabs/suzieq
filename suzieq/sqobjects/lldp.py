from suzieq.sqobjects.basicobj import SqObject


class LldpObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='lldp', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'ifname',
                                'query_str']
