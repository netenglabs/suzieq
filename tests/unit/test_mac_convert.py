from suzieq.shared.utils import convert_macaddr_format_to_colon


def test_mac_convert():
    '''Test all formats of MAC formats being converted to std format'''
    result = '50:9a:4c:36:a1:df'
    nullmac = '00:00:00:00:00:00'

    assert convert_macaddr_format_to_colon('509A:4C36:A1DF') == result, \
        'failed to convert 509A:4C36:A1DF'

    assert convert_macaddr_format_to_colon('509A.4C36.A1DF') == result, \
        'failed to convert 509A.4C36.A1DF'

    assert convert_macaddr_format_to_colon('509A-4C36-A1DF') == result, \
        'failed to convert 509A.4C36.A1DF'

    assert convert_macaddr_format_to_colon('509A4C36A1DF') == result, \
        'failed to convert 509A4C36A1DF'

    assert convert_macaddr_format_to_colon('50-9A-4C-36-A1-DF') == result, \
        'failed to convert 50-9A-4C-36-A1-DF'

    assert convert_macaddr_format_to_colon(
        '50-9Z-4C-36-A1-DF') == '50-9z-4c-36-a1-df', \
        'Incorrect conversion of 50-9Z-4C-36-A1-DF'

    assert convert_macaddr_format_to_colon(result) == result, \
        f'Failed to return {result} as is'

    assert convert_macaddr_format_to_colon(1) == nullmac, \
        f'Incorrect handling when int is passed'

    assert convert_macaddr_format_to_colon([1]) == nullmac, \
        f'Incorrect handling when list is passed'
