from suzieq.sqobjects.basicobj import SqObject
import pandas as pd
from suzieq.utils import humanize_timestamp


class InventoryObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='inventory', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'type',
                                'serial', 'vendor', 'status', 'model',
                                'query_str']
