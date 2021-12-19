from suzieq.sqobjects.basicobj import SqObject


class PathObj(SqObject):
    '''The object providing access to the path table'''

    def __init__(self, **kwargs):
        super().__init__(table='path', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'vrf', 'src', 'dest', 'query_str']
        self._valid_summarize_args = ['namespace', 'hostname', 'src',
                                      'dest', 'vrf', 'query_str']
