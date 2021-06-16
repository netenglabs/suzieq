import pytest

from tests.conftest import validate_host_shape
import pandas as pd


def validate_vlan_tbl(df: pd.DataFrame):
    '''Validate the VLAN table for all values'''

    assert (df.vlan != 0).all()
    assert (df.query('vlan != 1').interfaces.str.len() != 0).all()
    assert (df.state == 'active').all()
    assert (df.vlanName != '').all()


@ pytest.mark.parsing
@ pytest.mark.vlan
@ pytest.mark.parametrize('table', ['vlan'])
@ pytest.mark.parametrize('datadir',
                          ['tests/data/multidc/parquet-out/',
                           'tests/data/eos/parquet-out',
                           'tests/data/nxos/parquet-out',
                           'tests/data/junos/parquet-out'])
def test_lldp_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for VLAN table'''

    df = get_table_data

    assert not df.empty

    ns_dict = {
        'eos': 9,
        'junos': 7,
        'nxos': 9,
        'ospf-ibgp': 6,
    }

    validate_host_shape(df, ns_dict)
    validate_vlan_tbl(df)
