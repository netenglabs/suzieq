import pytest

import pandas as pd
from tests.conftest import DATADIR, validate_host_shape


def validate_evpnVni(df: pd.DataFrame):
    '''Validate the evpnVni table for all values'''

    njns_df = df.query('not os.str.startswith("junos")')
    jns_df = df.query('os.str.startswith("junos")')

    assert (jns_df.query('type == "L2"').vlan != 0).all()
    assert (njns_df.query('state == "up"').vlan != 0).all()
    assert (njns_df.ifname != '').all()

    assert (df.vni != 0).all()
    assert (df.priVtepIp != '').all()
    assert (df.type.isin(['L3', 'L2'])).all()
    assert (df.state.isin(['up', 'down'])).all()
    assert (df.replicationType.isin(['ingressBGP', 'multicast', ''])).all()
    assert (df.vrf != '').all()

    # pylint: disable=singleton-comparison
    assert (df.query('replicationType == "multicast"').mcastGroup.isin(
        ['', '0.0.0.0']) == False).all()  # noqa
    assert (df.query('os == "nxos"').routerMac != '').all()


@ pytest.mark.parsing
@ pytest.mark.evpnVni
@ pytest.mark.parametrize('table', ['evpnVni'])
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
def test_evpnVni_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for EVPN VNI table'''

    if 'basic_dual_bgp' in datadir:
        # No EVPN info in this one
        return

    df = get_table_data

    ns_dict = {
        'eos': 6,
        'junos': 4,
        'nxos': 6,
        'ospf-ibgp': 6,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_evpnVni(df)
