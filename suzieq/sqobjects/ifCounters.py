from suzieq.sqobjects.basicobj import SqObject


class IfCountersObj(SqObject):
    '''The object providing access to the interface counters table'''

    def __init__(self, **kwargs):
        super().__init__(table='ifCounters', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'ifname',
                                'query_str']
