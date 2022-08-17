import re

from suzieq.sqobjects.basicobj import SqObject
from suzieq.shared.utils import convert_macaddr_format_to_colon


class MacsObj(SqObject):
    '''The object providing access to the MAC table'''

    def __init__(self, **kwargs):
        super().__init__(table='macs', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'macaddr',
                                'remoteVtepIp', 'vlan', 'local', 'bd',
                                'moveCount', 'query_str']
        self._convert_args = {
            'macaddr': convert_macaddr_format_to_colon
        }
        self._unique_def_column = ['macaddr']

    def validate_get_input(self, **kwargs):
        for key, val in kwargs.items():
            if key == 'vlan':
                for ele in val:
                    if isinstance(ele, (int, float)):
                        continue
                    if (ele.startswith(('<', '>', '!')) and (
                            ele in ['<', '<=', '>', '>=', '!=', '!'])):
                        raise ValueError('operator must not be separated by '
                                         'space, as in "<20"')
                    words = re.split(r'<|<=|>|>=|!', ele)
                    try:
                        int(words[-1])
                    except Exception:
                        raise ValueError(f'Invalid VLAN value: {val}')
        return super().validate_get_input(**kwargs)
