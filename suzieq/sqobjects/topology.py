import typing

import pandas as pd
from suzieq.sqobjects.basicobj import SqObject


class TopologyObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='topology', **kwargs)
        self._sort_fields = ["namespace", "hostname", "ifname"]
        self._cat_fields = []
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'polled', 'query_str']
        self._valid_summarize_args = ['namespace', 'query_str']
