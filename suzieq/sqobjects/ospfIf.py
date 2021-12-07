from suzieq.sqobjects.basicobj import SqObject


class OspfIfObj(SqObject):
    '''The object providing access to the ospf interfaces table

    Used only from tables object. Use ospf object otherwise.
    '''

    def __init__(self, **kwargs):
        super().__init__(table='ospf', **kwargs)
        self._valid_get_args = ['namespace',
                                'hostname', 'columns', 'ifname', 'query_str']
