from ipaddress import ip_interface

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import validate_macaddr, validate_network


class AddressObj(SqObject):
    '''The object providing access to the address table'''

    def __init__(self, **kwargs):
        super().__init__(table='address', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'address', 'prefix',
                                'columns', 'ipvers', 'vrf', 'query_str',
                                'type', 'ifname']
        self._unique_def_column = ['ipAddress']

    def validate_get_input(self, **kwargs):
        if kwargs.get('prefix', []) and kwargs.get('address', []):
            raise AttributeError("Cannot specify address and prefix together")

        if kwargs.get('prefix', []):
            for p in kwargs['prefix']:
                if not validate_network(p):
                    raise ValueError("Invalid prefix specified")

        if kwargs.get('address', []):
            for a in kwargs['address']:
                try:
                    ip_interface(a)
                except ValueError:
                    if not validate_macaddr(a):
                        raise ValueError("Invalid address specified")

        return super().validate_get_input(**kwargs)
