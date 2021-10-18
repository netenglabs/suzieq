import pytest


import pandas as pd
from tests.conftest import DATADIR, validate_host_shape


def validate_lldp_tbl(df: pd.DataFrame):
    '''Validate the LLDP table for all values'''

    assert (df.ifname != "").all()
    assert (df.peerHostname != "").all()
    assert (df.query('subtype == "interface name"').peerIfname != "").all()
    assert (df.query('subtype == "locally assigned"').peerIfindex != "").all()
    assert (df.subtype.isin(['interface name', 'mac address',
                             'locally assigned'])).all()


@ pytest.mark.parsing
@ pytest.mark.lldp
@ pytest.mark.parametrize('table', ['lldp'])
@ pytest.mark.parametrize('datadir', DATADIR)
def test_lldp_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for LLDP table'''

    df = get_table_data

    ns_dict = {
        'eos': 9,
        'junos': 7,
        'nxos': 9,
        'ospf-ibgp': 10,
        'vmx': 5,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_lldp_tbl(df)
