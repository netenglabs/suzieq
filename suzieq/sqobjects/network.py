import pandas as pd

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import humanize_timestamp


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

        addr = kwargs.get('address', '')
        asn = kwargs.get('asn', '')

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if not addr and not asn:
            raise AttributeError('Must specify address or asn')

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
