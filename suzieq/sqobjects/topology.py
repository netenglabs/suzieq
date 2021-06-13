from typing import List

import pandas as pd
from suzieq.sqobjects.basicobj import SqObject


class TopologyObj(SqObject):
    def __init__(self, **kwargs):
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

    def summarize(self, namespace: List[str] = [], hostname: List[str] = [],
                  via: List[str] = [], query_str='') -> pd.DataFrame:
        if self.columns != ["default"]:
            self.summarize_df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with summarize']})
            return self.summarize_df
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine.summarize(namespace=namespace, hostname=hostname,
                                     via=via, query_str=query_str)
