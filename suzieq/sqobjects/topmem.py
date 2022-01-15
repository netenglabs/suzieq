from suzieq.sqobjects.basicobj import SqObject


class TopmemObj(SqObject):
    '''The object providing access to the topmem table'''

    def __init__(self, **kwargs):
        super().__init__(table='topmem', **kwargs)
        self._valid_get_args = ['namespace',
                                'hostname', 'columns', 'query_str']
