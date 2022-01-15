from suzieq.sqobjects.basicobj import SqObject


class FsObj(SqObject):
    '''The object providing access to the filesystem(fs) table'''

    def __init__(self, **kwargs):
        super().__init__(table='fs', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'mountPoint', 'usedPercent', 'query_str']
        self._unique_def_column = ['fstype']
