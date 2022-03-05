from suzieq.sqobjects.basicobj import SqObject


class OspfNbrObj(SqObject):
    '''The object providing access to the ospf neighbor table

    For use from tables obj only. Use ospf object instead.
    '''

    def __init__(self, **kwargs):
        super().__init__(table='ospfNbr', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'ifname',
                                'vrf', 'area', 'query_str']
