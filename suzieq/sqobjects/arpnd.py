from suzieq.sqobjects.basicobj import SqObject


class ArpndObj(SqObject):

    def __init__(self, **kwargs):
        super().__init__(table='arpnd', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'ipAddress',
                                'columns', 'oif', 'macaddr', 'query_str']
