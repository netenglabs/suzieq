import re
from suzieq.sqobjects.basicobj import SqObject


class MacsObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='macs', **kwargs)

    def validate_input(self, **kwargs):
        for key in kwargs:
            if key == 'vlan':
                for ele in kwargs[key]:
                    if (ele.startswith(('<', '>', '!')) and (
                            ele in ['<', '<=', '>', '>=', '!=', '!'])):
                        raise ValueError('operator must not be separated by '
                                         'space, as in "<20"')
                    words = re.split(r'<|<=|>|>=|!', ele)
                    try:
                        int(words[-1])
                    except Exception:
                        raise ValueError(f'Invalid VLAN value: {kwargs[key]}')
