from suzieq.sqobjects.basicobj import SqObject


class DevconfigObj(SqObject):
    '''The object providing access to the device config table'''

    def __init__(self, **kwargs):
        super().__init__(table='devconfig', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']
