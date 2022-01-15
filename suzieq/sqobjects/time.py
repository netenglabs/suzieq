from suzieq.sqobjects.basicobj import SqObject


class TimeObj(SqObject):
    '''The object providing access to the time table'''

    def __init__(self, **kwargs):
        super().__init__(table='time', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']
