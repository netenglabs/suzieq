from typing import List

import pandas as pd
from suzieq.sqobjects.basicobj import SqObject


class TopologyObj(SqObject):
    '''The object providing access to the virtual table: topology'''

    def __init__(self, **kwargs):
        '''Init routine'''
        super().__init__(table='topology', **kwargs)
        self._sort_fields = ["namespace", "hostname", "ifname"]
        self._cat_fields = []
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'polled', 'ifname', 'via', 'vrf', 'asn',
                                'area', 'peerHostname', 'afiSafi', 'query_str']
        self._valid_summarize_args = ['namespace', 'hostname', 'via', 'vrf',
                                      'asn', 'area', 'query_str']
        self._valid_arg_vals = {
            'polled': ['True', 'False', 'true', 'false', '']
        }
        self._valid_summarize_args = ['namespace', 'hostname', 'via',
                                      'query_str']

    def get(self, **kwargs) -> pd.DataFrame:
        view = kwargs.get('view', self.view)
        if view == 'all':
            raise AttributeError("Cannot use 'view=all' with this table")
        return super().get(**kwargs)

    def _get_empty_cols(self, columns: List[str], fun: str, **kwargs) \
            -> List[str]:
        if fun == 'get' and columns in [['default'], ['*']]:
            def_vias = ['bgp', 'lldp', 'ospf']
            via = kwargs.get('via', []) or def_vias
            cols = self.schema.get_display_fields(columns)
            drop_cols = []
            if 'arpnd' not in via:
                drop_cols += ['arpnd', 'arpndBidir']
            if 'bgp' not in via:
                drop_cols += ['bgp', 'asn', 'peerAsn']
            if 'ospf' not in via:
                drop_cols += ['ospf', 'area']
            if 'lldp' not in via:
                drop_cols += ['lldp']

            if via == ['bgp']:
                # if only bgp is specified, the ifname column is not returned
                drop_cols += ['ifname']

            if drop_cols:
                cols = [c for c in cols if c not in drop_cols]
            return cols

        return super()._get_empty_cols(columns, fun, **kwargs)
