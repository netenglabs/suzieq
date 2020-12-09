from suzieq.sqobjects.basicobj import SqObject


class DeviceObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='device', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']
