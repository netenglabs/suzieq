import pytest
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.path import PathObj

# valid dataframe extracted from test data
df = pd.DataFrame({
    'pathid': {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2},
    'hopCount': {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 0, 6: 1, 7: 2, 8: 3, 9: 4},
    'namespace': {0: 'junos', 1: 'junos', 2: 'junos', 3: 'junos', 4: 'junos',
                  5: 'junos', 6: 'junos', 7: 'junos', 8: 'junos', 9: 'junos'},
    'hostname': {0: 'server101', 1: 'leaf01', 2: 'spine01', 3: 'leaf02',
                 4: 'server202', 5: 'server101', 6: 'leaf01', 7: 'spine02',
                 8: 'leaf02', 9: 'server202'},
    'iif': {0: 'eth1', 1: 'xe-0/0/2', 2: 'xe-0/0/0.0', 3: 'xe-0/0/0.0',
            4: 'eth1', 5: 'eth1', 6: 'xe-0/0/2', 7: 'xe-0/0/0.0',
            8: 'xe-0/0/1.0', 9: 'eth1'},
    'oif': {0: 'eth1', 1: 'xe-0/0/0.0', 2: 'xe-0/0/1.0', 3: 'xe-0/0/3',
            4: 'eth1', 5: 'eth1', 6: 'xe-0/0/1.0', 7: 'xe-0/0/1.0',
            8: 'xe-0/0/3', 9: 'eth1'},
    'vrf': {0: 'default', 1: 'evpn-vrf', 2: 'default', 3: 'evpn-vrf',
            4: 'default', 5: 'default', 6: 'evpn-vrf', 7: 'default',
            8: 'evpn-vrf', 9: 'default'},
    'isL2': {0: False, 1: True, 2: True, 3: False, 4: False, 5: False,
             6: True, 7: True, 8: False, 9: False},
    'overlay': {0: False, 1: False, 2: True, 3: True, 4: False, 5: False,
                6: False, 7: True, 8: True, 9: False},
    'mtuMatch': {0: True, 1: False, 2: True, 3: True, 4: False, 5: True,
                 6: False, 7: True, 8: True, 9: False},
    'inMtu': {0: 9216, 1: 1514, 2: 9200, 3: 9200, 4: 9216, 5: 9216, 6: 1514,
              7: 9200, 8: 9200, 9: 9216},
    'outMtu': {0: 9216, 1: 9200, 2: 9200, 3: 1514, 4: 9216, 5: 9216,
               6: 9200, 7: 9200, 8: 1514, 9: 9216},
    'protocol': {0: '', 1: 'evpn', 2: 'ospf', 3: 'evpn', 4: '', 5: '',
                 6: 'evpn', 7: 'ospf', 8: 'evpn', 9: ''},
    'ipLookup': {0: '172.16.0.0/16', 1: '172.16.3.202/32', 2: '10.0.0.12',
                 3: '172.16.3.202/32', 4: '', 5: '172.16.0.0/16',
                 6: '172.16.3.202/32', 7: '10.0.0.12', 8: '172.16.3.202/32',
                 9: ''},
    'vtepLookup': {0: '', 1: '10.0.0.12', 2: '10.0.0.12', 3: '', 4: '', 5: '',
                   6: '10.0.0.12', 7: '10.0.0.12', 8: '', 9: ''},
    'macLookup': {0: '', 1: '', 2: '', 3: '', 4: '', 5: '', 6: '', 7: '',
                  8: '', 9: ''},
    'nexthopIp': {0: '172.16.1.254',
                  1: '10.0.0.21', 2: '10.0.0.12', 3: '172.16.3.202', 4: '',
                  5: '172.16.1.254', 6: '10.0.0.22', 7: '10.0.0.12',
                  8: '172.16.3.202', 9: ''},
    'error': {0: '', 1: 'Hop MTU < Src Mtu', 2: 'Hop MTU < Src Mtu',
              3: 'Hop MTU < Src Mtu', 4: '', 5: '', 6: 'Hop MTU < Src Mtu',
              7: 'Hop MTU < Src Mtu', 8: 'Hop MTU < Src Mtu', 9: ''},
    'timestamp': {0: pd.Timestamp('2021-01-05T12'),
                  1: pd.Timestamp('2021-01-05T12'),
                  2: pd.Timestamp('2021-01-05T12'),
                  3: pd.Timestamp('2021-01-05T12'),
                  4: pd.Timestamp('2021-01-05T12'),
                  5: pd.Timestamp('2021-01-05T12'),
                  6: pd.Timestamp('2021-01-05T12'),
                  7: pd.Timestamp('2021-01-05T12'),
                  8: pd.Timestamp('2021-01-05T12'),
                  9: pd.Timestamp('2021-01-05T12')}})


@pytest.mark.cli
@pytest.mark.parametrize('output_format', ['json', 'csv', 'markdown',
                                           'devconfig', ''])
# pylint: disable=unused-argument
def test_cli_outputs_with_error(output_format, setup_nubia):
    '''Test output generation with errors'''

    sqcmd = SqCommand(format=output_format, sqobj=PathObj)
    # pylint: disable=protected-access
    assert sqcmd._gen_output(df) == 1


@pytest.mark.cli
@pytest.mark.parametrize('output_format', ['json', 'csv', 'markdown',
                                           'devconfig', ''])
# pylint: disable=unused-argument
def test_cli_outputs_without_error(output_format, setup_nubia):
    '''Test output generation without errors'''

    sqcmd = SqCommand(format=output_format, sqobj=PathObj)
    # pylint: disable=protected-access
    assert sqcmd._gen_output(df.drop(columns=['error'])) == 0
