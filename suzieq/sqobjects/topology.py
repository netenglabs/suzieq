from suzieq.sqobjects.basicobj import SqObject


class TopologyObj(SqObject):
    '''The object providing access to the virtual table: topology'''

    def __init__(self, **kwargs):
        '''Init routine'''
        super().__init__(table='topology', **kwargs)
        self._sort_fields = ["namespace", "hostname", "ifname"]
        self._cat_fields = []
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'polled', 'ifname', 'via', 'peerHostname',
                                'query_str']
        self._valid_summarize_args = ['namespace', 'hostname', 'via',
                                      'query_str']
        self._valid_arg_vals = {
            'polled': ['True', 'False', 'true', 'false', '']
        }
        self._valid_summarize_args = ['namespace', 'hostname', 'via',
                                      'query_str']
