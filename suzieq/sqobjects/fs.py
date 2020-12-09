from suzieq.sqobjects.basicobj import SqObject


class FsObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='fs', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'mountPoint', 'usedPercent', 'query_str']
