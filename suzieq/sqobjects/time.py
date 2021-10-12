from suzieq.sqobjects.basicobj import SqObject


class TimeObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='time', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'query_str']
