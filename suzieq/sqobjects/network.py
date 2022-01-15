from ipaddress import ip_address
import re
import pandas as pd

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import (humanize_timestamp,
                                 convert_macaddr_format_to_colon)


class NetworkObj(SqObject):
    '''The object providing access to the virtual table: network'''

    def __init__(self, **kwargs):
        super().__init__(table='network', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'version', 'os',
                                'model', 'vendor', 'columns', 'query_str']
        self._valid_find_args = ['namespace', 'hostname', 'vrf', 'vlan',
                                 'address', 'query_str']
        self._unique_def_column = ['namespace']

    def find(self, **kwargs) -> pd.DataFrame():
        '''Find network attach point for a given address'''

        addresses = kwargs.get('address', '')

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if not addresses:
            raise AttributeError('Must specify address or asn')

        for addr in addresses:
            try:
                ip_address(addr)
            except ValueError:
                addr = convert_macaddr_format_to_colon(addr)
                if not re.match(
                        "[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$",
                        addr):
                    return pd.DataFrame(
                        {'error': [f'Not valid IP or MAC address: {addr}']})
        try:
            self._check_input_for_valid_args(self._valid_find_args, **kwargs)
        except (ValueError, AttributeError) as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        return self.engine.find(**kwargs)

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the timestamp fields'''
        if df.empty:
            return df

        if 'lastUpdate' in df.columns:
            df['lastUpdate'] = humanize_timestamp(df.lastUpdate,
                                                  self.cfg.get('analyzer', {})
                                                  .get('timezone', None))

        return super().humanize_fields(df)
