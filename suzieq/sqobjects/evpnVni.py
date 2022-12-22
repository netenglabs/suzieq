from typing import List
from suzieq.sqobjects.basicobj import SqObject


class EvpnvniObj(SqObject):
    '''The object providing access to the evpnVni table'''

    def __init__(self, **kwargs):
        super().__init__(table='evpnVni', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'vni',
                                'priVtepIp', 'query_str']
        self._valid_assert_args = self._valid_get_args + ['result']
        self._valid_arg_vals = {
            'result': ['all', 'pass', 'fail'],
        }

    def _get_empty_cols(self, columns: List[str], fun: str, **kwargs) \
            -> List[str]:
        if fun == 'assert':
            if columns in [['default'], ['*']]:
                # this is the copy of engine/pandas/self._assert_result_cols
                return ['namespace', 'hostname', 'vni', 'type', 'vrf',
                        'macaddr', 'timestamp', 'result', 'assertReason']
        return super()._get_empty_cols(columns, fun, **kwargs)
