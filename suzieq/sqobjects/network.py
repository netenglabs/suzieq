from pandas import DataFrame
from suzieq.sqobjects.basicobj import SqObject


class NetworkObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='network', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'version',
                                'os', 'model', 'vendor', 'columns', 'query_str']
        self._valid_find_args = ['namespace', 'hostname', 'vrf', 'vlan',
                                 'address', 'asn', 'resolve_bond']

    def find(self, **kwargs):

        addr = kwargs.get('address', '')
        asn = kwargs.get('asn', '')

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if not addr and not asn:
            raise AttributeError('Must specify address or asn')

        try:
            self._check_input_for_valid_args(self._valid_find_args, **kwargs)
        except Exception as error:
            df = DataFrame({'error': [f'{error}']})
            return df

        return self.engine.find(**kwargs)
