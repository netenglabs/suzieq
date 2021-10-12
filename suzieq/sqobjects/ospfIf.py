from suzieq.sqobjects.basicobj import SqObject


class OspfIfObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='ospf', **kwargs)
        self._valid_get_args = ['namespace',
                                'hostname', 'columns', 'ifname', 'query_str']
