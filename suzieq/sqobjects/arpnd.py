from ipaddress import ip_interface

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import (convert_macaddr_format_to_colon,
                                 validate_macaddr)
from suzieq.shared.utils import validate_network


class ArpndObj(SqObject):
    '''The object providing access to the arp/nd table'''

    def __init__(self, **kwargs):
        super().__init__(table='arpnd', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'ipAddress', 'prefix',
                                'columns', 'oif', 'macaddr', 'query_str']
        self._convert_args = {
            'macaddr': convert_macaddr_format_to_colon
        }

    def validate_get_input(self, **kwargs):
        if kwargs.get('prefix', []) and kwargs.get('ipAddress', []):
            raise AttributeError("Cannot specify address and prefix together")

        if kwargs.get('prefix', []):
            for p in kwargs['prefix']:
                if not validate_network(p):
                    raise ValueError("Invalid prefix specified")

        if kwargs.get('ipAddress', []):
            for a in kwargs['ipAddress']:
                try:
                    ip_interface(a)
                except ValueError:
                    raise ValueError("Invalid IP address specified")

        if kwargs.get('macaddr', []):
            for m in kwargs['macaddr']:
                if not validate_macaddr(m):
                    raise ValueError("Invalid mac address specified")

        self._unique_def_column = ['ipAddress']
        return super().validate_get_input(**kwargs)
