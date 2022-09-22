from ipaddress import ip_address
import pandas as pd

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import (humanize_timestamp, validate_macaddr,
                                 convert_macaddr_format_to_colon)


class NetworkObj(SqObject):
    '''The object providing access to the virtual table: network'''

    def __init__(self, **kwargs):
        super().__init__(table='network', **kwargs)
        self._valid_find_args = ['namespace', 'hostname', 'vrf', 'vlan',
                                 'address', 'query_str']

    def find(self, **kwargs) -> pd.DataFrame():
        '''Find network attach point for a given address'''

        addresses = kwargs.get('address', '')
        columns = kwargs.pop('columns', self.columns)

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if not addresses:
            raise AttributeError('Must specify address')

        for addr in addresses:
            try:
                ip_address(addr)
            except ValueError:
                addr = convert_macaddr_format_to_colon(addr)
                if not validate_macaddr(addr):
                    return pd.DataFrame(
                        {'error': [f'Not valid IP or MAC address: {addr}']})
        try:
            self._check_input_for_valid_args(self._valid_find_args, **kwargs)
        except (ValueError, AttributeError) as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        result = self.engine.find(**kwargs, columns=columns)
        if self._is_result_empty(result):
            fields = self._get_empty_cols(columns, 'find')
            return self._empty_result(fields)
        return result

    def get(self, **kwargs) -> pd.DataFrame:
        return self._run_deprecated_function(table='namespace', command='get',
                                             **kwargs)

    def summarize(self, **kwargs) -> pd.DataFrame:
        return self._run_deprecated_function(table='namespace',
                                             command='summarize', **kwargs)

    def top(self, what: str = '', count: int = 5, reverse: bool = False,
            **kwargs) -> pd.DataFrame:
        return self._run_deprecated_function(table='namespace', command='top',
                                             what=what, count=count,
                                             reverse=reverse, **kwargs)

    def unique(self, **kwargs) -> pd.DataFrame:
        return self._run_deprecated_function(table='namespace',
                                             command='unique', **kwargs)

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp fields'''
        if df.empty:
            return df

        if 'lastUpdate' in df.columns:
            df['lastUpdate'] = humanize_timestamp(df.lastUpdate,
                                                  self.cfg.get('analyzer', {})
                                                  .get('timezone', None))

        return super().humanize_fields(df)
