import pytest
import pandas as pd
import numpy as np

from tests.conftest import create_dummy_config_file
from suzieq.sqobjects import get_sqobject


def _validate_ethernet_if(df: pd.DataFrame):
    '''Validate state in interfaces in UP state'''

    # We don't collect speed for Linux servers, vEOS doesn't provide speed
    # A bunch of internal Junos interface names including SVIs show up as
    # ethernet interfaces
    assert (df.query('(os != "linux") and (namespace != "eos")')
            .speed != 0).all()


def _validate_bridged_if(df: pd.DataFrame):
    '''Validate state in interfaces in UP state'''
    for row in df.itertuples():
        assert ((len(row.ipAddressList) == 0) and
                (len(row.ip6AddressList) == 0))


def _validate_bond_if(df: pd.DataFrame):
    '''Validate bond interfaces'''

    # We don't collect speed for Linux servers, vEOS doesn't provide speed
    assert (df.query('(os != "linux") and (namespace != "eos") '
                     'and (state == "up")').speed != 0).all()


def _validate_vrf_if(df: pd.DataFrame):
    '''Validate VRF interfaces'''

    assert (df.master == "").all()
    cldf = df.query('os == "cumulus"').reset_index(drop=True)
    if not cldf.empty:
        assert (cldf.macaddr != "00:00:00:00:00:00").all()

    nxosdf = df.query('os == "nxos"').reset_index(drop=True)
    if not nxosdf.empty:
        assert not nxosdf.query('ifname != "management" and '
                                'routeDistinguisher != ""').empty
        assert not nxosdf.query('routeDistinguisher != "0:0" and '
                                'vni != 0').empty
        assert (nxosdf.macaddr == "00:00:00:00:00:00").all()


def _validate_svi_and_subif(df: pd.DataFrame):
    '''Validate SVI and VLAN subif'''
    assert (df.query('state == "up"').vlan != 0).all()
    for row in df.itertuples():
        if row.ifname == "Vlan999" or row.state != "up":
            continue
        assert ((len(row.ipAddressList) != 0) or
                (len(row.ip6AddressList) != 0))


def _validate_vxlan_if(df: pd.DataFrame):
    '''Validate VXLAN subif'''

    # Internal consistency, make sure its part of a bridge
    assert (df.master == 'bridge').all()
    assert (df.speed == 0).all()

    # Individual NOS testing
    cldf = df.query('os == "cumulus"').reset_index(drop=True)
    if not cldf.empty:
        assert (cldf.vni != 0).all()
        assert (cldf.vlan != 0).all()
        assert (cldf.srcVtepIp != '').all()
        assert (cldf.macaddr != "00:00:00:00:00:00").all()

    restdf = df.query('os != "cumulus"').reset_index(drop=True)
    if not restdf.empty:
        assert (restdf.macaddr == "00:00:00:00:00:00").all()


def _validate_loopback_if(df: pd.DataFrame):
    '''Validate loopback interfaces'''
    pass


def _validate_null_if(df: pd.DataFrame):
    '''Validate Null interfaces from XR'''
    assert (df.speed == 0).all()


def _validate_tunnel_te_if(df: pd.DataFrame):
    '''Validate Null interfaces from XR'''
    assert (df.speed == 0).all()
    assert (df.master != "").all()


def _validate_gre_if(df: pd.DataFrame):
    '''Validate GRE interfaces'''
    pass


def _validate_junos_vtep_if(df: pd.DataFrame):
    '''Validate Junos VTEP interfaces'''
    pass


@pytest.mark.parsing
@pytest.mark.interface
@pytest.mark.parametrize('datadir',
                         ['tests/data/multidc/parquet-out/',
                          'tests/data/eos/parquet-out',
                          'tests/data/nxos/parquet-out',
                          'tests/data/junos/parquet-out'])
def test_interfaces(datadir):
    '''Main workhorse routine to test interfaces'''

    print(f'testing with {datadir}')

    cfgfile = create_dummy_config_file(datadir=datadir)

    df = get_sqobject('interfaces')(config_file=cfgfile).get(columns=['*'])
    device_df = get_sqobject('device')(config_file=cfgfile) \
        .get(columns=['namespace', 'hostname', 'os'])

    if not device_df.empty:
        df = df.merge(device_df, on=['namespace', 'hostname']) \
               .fillna({'os': ''})

    validation_fns = {'bond': _validate_bond_if,
                      'bond_slave': _validate_bond_if,
                      'bridge': None,
                      'ethernet': _validate_ethernet_if,
                      'flexible-ethernet': None,
                      'flexible-tunnel-interface': None,
                      'gre': _validate_gre_if,
                      'internal': None,
                      'ip-over-ip': None,
                      'logical': None,
                      'loopback': _validate_loopback_if,
                      'lsi': None,
                      'macvlan': None,
                      'mgmt-vlan': None,
                      'null': _validate_null_if,
                      'pim-decapsulator': None,
                      'pim-encapsulator': None,
                      'pppoe': None,
                      'remote-beb': None,
                      'software-pseudo': None,
                      'subinterface': None,
                      'tap': None,
                      'tunnel-te': _validate_tunnel_te_if,
                      'virtual': None,
                      'vlan': _validate_svi_and_subif,
                      'vlan-l2': None,
                      'vtep': _validate_junos_vtep_if,
                      'vxlan': _validate_vxlan_if,
                      'vrf': _validate_vrf_if
                      }

    assert not df.empty
    assert df.state.isin(['up', 'down', 'notConnected']).all()
    assert df.adminState.isin(['up', 'down']).all()

    assert (df.type != "").all()
    assert df.type.isin(validation_fns.keys()).all()

    for iftype in validation_fns.keys():
        if validation_fns[iftype]:
            subdf = df.query(f'type == "{iftype}"').reset_index(drop=True)
            if not subdf.empty:
                validation_fns[iftype](subdf)

                assert (subdf.macaddr.str.len() == 17).all()
                assert (subdf.macaddr.str.contains(':')).all()
        assert (df.mtu != 0).all()
