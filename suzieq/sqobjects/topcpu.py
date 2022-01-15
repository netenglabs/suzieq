from suzieq.sqobjects.basicobj import SqObject


class TopcpuObj(SqObject):
    '''The object providing access to the topcpu table'''

    def __init__(self, **kwargs):
        super().__init__(table='topcpu', **kwargs)
        self._valid_get_args = ['namespace',
                                'hostname', 'columns', 'query_str']
