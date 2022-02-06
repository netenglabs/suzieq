from suzieq.sqobjects.basicobj import SqObject


class PolledNodesObj(SqObject):
    '''The object providing access to currently polled nodes
    '''

    def __init__(self, **kwargs):
        super().__init__(table='polledNodes', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'address', 'port',
                                'query_str']
