import typing

import pandas as pd
from suzieq.sqobjects.basicobj import SqObject


class TopologyObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='topology', **kwargs)
        self._sort_fields = ["namespace", "hostname", 'columns', ]
        self._cat_fields = []
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'polled_neighbor', 'query_str']

    # overriding parent because we want to take more arguments than the standard
    def summarize(self, namespace: typing.List[str] = [],
                  hostname: typing.List[str] = [],
                  polled_neighbor=None, query_str: str = '') -> pd.DataFrame:
        if self.columns != ["default"]:
            self.summarize_df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with summarize']})
            return self.summarize_df

        return self.engine.summarize(namespace=namespace, hostname=hostname,
                                     query_str=query_str,
                                     polled_neighbor=polled_neighbor)
