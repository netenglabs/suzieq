from suzieq.sqobjects.basicobj import SqObject
import pandas as pd
from suzieq.utils import humanize_timestamp


class DevconfigObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='devconfig', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']
