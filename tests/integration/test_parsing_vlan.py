import pytest
import warnings

from tests.conftest import DATADIR, validate_host_shape
import pandas as pd


def validate_vlan_tbl(df: pd.DataFrame):
    '''Validate the VLAN table for all values'''

    assert (df.vlan != 0).all()
    if not (df.query('vlan != 1').interfaces.str.len() != 0).all():
        warnings.warn('Some VLANs not assigned to any interface')
    assert (df.state == 'active').all()
    assert (df.vlanName != '').all()


@ pytest.mark.parsing
@ pytest.mark.vlan
@ pytest.mark.parametrize('table', ['vlan'])
@ pytest.mark.parametrize('datadir', DATADIR)
def test_vlan_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for VLAN table'''

    df = get_table_data

    ns_dict = {
        'eos': 9,
        'junos': 7,
        'nxos': 9,
        'ospf-ibgp': 6,
        'mixed': 6,
    }

    if datadir.endswith(('vmx/parquet-out')):
        # mixed dataset has no evpn
        assert (True)
        return

    assert not df.empty

    validate_host_shape(df, ns_dict)
    validate_vlan_tbl(df)
