from suzieq.sqobjects.basicobj import SqObject


class IgmpObj(SqObject):
    '''The object providing access to the igmp table
    '''

    def __init__(self, **kwargs):
        super().__init__(table='igmp', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'group', 'interfaceList', 'vrf',
                                'flag', 'query_str']

