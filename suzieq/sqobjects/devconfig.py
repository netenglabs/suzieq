from suzieq.sqobjects.basicobj import SqObject


class DevconfigObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='devconfig', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']
