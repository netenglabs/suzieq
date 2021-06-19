from suzieq.sqobjects.basicobj import SqObject
from suzieq.utils import convert_macaddr_format_to_colon


class ArpndObj(SqObject):

    def __init__(self, **kwargs):
        super().__init__(table='arpnd', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'ipAddress',
                                'columns', 'oif', 'macaddr', 'query_str']
        self._convert_args = {
            'macaddr': convert_macaddr_format_to_colon
        }
