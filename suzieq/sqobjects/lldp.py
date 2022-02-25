from suzieq.sqobjects.basicobj import SqObject


class LldpObj(SqObject):
    '''The object providing access to the lldp table'''

    def __init__(self, **kwargs):
        super().__init__(table='lldp', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'ifname',
                                'peerMacaddr', 'peerHostname', 'use_bond',
                                'query_str']
