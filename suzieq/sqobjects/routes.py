import re
import pandas as pd

from suzieq.sqobjects.basicobj import SqObject


class RoutesObj(SqObject):
    '''The object providing access to the routes table'''

    def __init__(self, **kwargs):
        super().__init__(table='routes', **kwargs)
        self._addnl_filter = 'metric != 4278198272'
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'prefix',
                                'vrf', 'protocol', 'prefixlen', 'ipvers',
                                'add_filter', 'address', 'query_str']
        self._unique_def_column = ['prefix']
        self._valid_summarize_args += ['vrf']

    def validate_get_input(self, **kwargs):
        '''Validate input to show'''
        if kwargs.get('prefixlen', ''):
            p_match = re.fullmatch(r'([<>][=]?|[!])?[ ]?([0-9]+)',
                                   kwargs['prefixlen'])
            if p_match:
                plen = int(p_match.group(2))
                operator = str(p_match.group(1))
            else:
                raise ValueError("Invalid prefixlen query: it must be of the "
                                 "form '[<|<=|>=|>|!] length' (i.e. '>= 24')")
            if (not (0 <= plen <= 128) or
               (plen == 128 and operator.startswith('>')) or
               (not plen and operator.startswith('<'))):
                raise ValueError("Invalid prefixlen: "
                                 "value should be between 0 and 128")

        return super().validate_get_input(**kwargs)

    def lpm(self, **kwargs) -> pd.DataFrame:
        '''Get the lpm for the given address'''
        kwargs.pop('ignore_warning', None)
        columns = kwargs.pop('columns', self.columns)
        if not kwargs.get("address", None):
            raise AttributeError('ip address is mandatory parameter')
        if isinstance(kwargs['address'], list):
            if len(kwargs['address']) > 1:
                raise AttributeError('Just one address at a time')
            kwargs['address'] = kwargs['address'][0]
        result = self.engine.lpm(**kwargs, columns=columns)
        if self._is_result_empty(result):
            fields = self._get_empty_cols(columns, 'lpm')
            return self._empty_result(fields)
        return result
