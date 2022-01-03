import pytest

import warnings
import pandas as pd
from ipaddress import ip_interface

from tests.conftest import DATADIR, validate_host_shape
from suzieq.shared.utils import MISSING_SPEED


def validate_speed_if(df: pd.DataFrame):
    '''Validate interface speed'''
    # if not df.empty:
    #    assert(df.speed != MISSING_SPEED).all()
    pass


def _validate_ethernet_if(df: pd.DataFrame, _):
    '''Validate state in interfaces in UP state'''

    # We don't collect speed for Linux servers, vEOS doesn't provide speed
    # A bunch of internal Junos interface names including SVIs show up as
    # ethernet interfaces
    assert (df.query('(not (os.isin(["linux", "sonic"]) or '
                     'namespace == "eos" or '
                     'hostname.isin(["leaf6-eos", "leaf5-eos"]))) and '
                     '(state == "up") and ifname != "em1"')
            .speed != MISSING_SPEED).all()


def _validate_bridged_if(df: pd.DataFrame, _):
    '''Validate state in interfaces in UP state'''
    for row in df.itertuples():
        assert ((len(row.ipAddressList) == 0) and
                (len(row.ip6AddressList) == 0))


def _validate_junos_speed_if(df: pd.DataFrame):
    '''
    Validate junos interface speed

    All logical and physical interfaces must have the same speed
    '''
    ifnames = dict()
    for _, row in df.iterrows():
        pIfname = row["ifname"].split(".")[0]
        hostAndPIfname = f'{row["hostname"]}{pIfname}'
        if pIfname != row["ifname"]:
            # logical interface
            if ifnames.get(hostAndPIfname, '') == '':
                ifnames[hostAndPIfname] = []
            ifnames[hostAndPIfname].append(row["speed"])
    for ifSpeeds in ifnames.values():
        assert(len(set(ifSpeeds)) == 1)


def _validate_bond_if(df: pd.DataFrame, full_df: pd.DataFrame):
    '''Validate bond interfaces'''

    # We don't collect speed for Linux servers, vEOS doesn't provide speed
    assert (df.query('~os.isin(["linux", "eos"]) '
                     'and (state == "up")').speed != 0).all()

    # for every bond interface, verify we have info about its members
    for row in df.itertuples():
        if row.type != 'bond':
            continue
        assert not full_df.query(f'namespace=="{row.namespace}" and '
                                 f'hostname=="{row.hostname}" and '
                                 f'ifname == "{row.ifname}"').empty


def _validate_vrf_if(df: pd.DataFrame, _):
    '''Validate VRF interfaces'''

    assert (df.master == "").all()
    cldf = df.query('os == "cumulus"').reset_index(drop=True)
    if not cldf.empty:
        assert (cldf.macaddr != "00:00:00:00:00:00").all()

    nxosdf = df.query('os == "nxos" and namespace != "mixed"') \
        .reset_index(drop=True)
    if not nxosdf.empty:
        assert not nxosdf.query('ifname != "management" and '
                                'routeDistinguisher != ""').empty
        assert (nxosdf.macaddr == "00:00:00:00:00:00").all()
        assert not nxosdf.query('routeDistinguisher != "0:0" and '
                                'vni != 0').empty


def _validate_svi_and_subif(df: pd.DataFrame, _):
    '''Validate SVI and VLAN subif'''
    assert (df.query('state == "up"').vlan != 0).all()
    for row in df.itertuples():
        if row.ifname == "Vlan999" or row.state != "up":
            continue
        if ((len(row.ipAddressList) == 0) and
                (len(row.ip6AddressList) == 0)):
            warnings.warn("VLAN {} has no IP address".format(row.ifname))
        assert(row.state == "up" and row.macaddr != "00:00:00:00:00:00")
        assert all(ip_interface(x) for x in row.ipAddressList)
        assert all(ip_interface(x) for x in row.ip6AddressList)


def _validate_vxlan_if(df: pd.DataFrame, _):
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

    restdf = df.query('~os.isin(["cumulus", "sonic"])').reset_index(drop=True)
    if not restdf.empty:
        assert (restdf.macaddr == "00:00:00:00:00:00").all()


def _validate_loopback_if(df: pd.DataFrame, _):
    '''Validate loopback interfaces'''
    pass


def _validate_null_if(df: pd.DataFrame, _):
    '''Validate Null interfaces from XR'''
    assert (df.speed == 0).all()


def _validate_tunnel_te_if(df: pd.DataFrame, _):
    '''Validate Null interfaces from XR'''
    assert (df.speed == 0).all()
    assert (df.master != "").all()


def _validate_gre_if(df: pd.DataFrame, _):
    '''Validate GRE interfaces'''
    pass


def _validate_junos_vtep_if(df: pd.DataFrame, _):
    '''Validate Junos VTEP interfaces'''
    pass


@pytest.mark.parsing
@pytest.mark.interface
@pytest.mark.parametrize('table', ['interfaces'])
@pytest.mark.parametrize('datadir', DATADIR)
def test_interfaces(table, datadir, get_table_data):
    '''Main workhorse routine to test interfaces'''

    df = get_table_data

    validation_fns = {'adaptive-services': None,
                      'bond': _validate_bond_if,
                      'bond_slave': _validate_bond_if,
                      'bridge': None,
                      'ethernet': _validate_ethernet_if,
                      'ethernet-ccc': _validate_ethernet_if,
                      'flexible-ethernet': None,
                      'flexible-tunnel-interface': None,
                      'gre': _validate_gre_if,
                      'igbe': None,
                      'internal': None,
                      'ip-over-ip': None,
                      'linkservice': None,
                      'logical': None,
                      'logical-tunnel': None,
                      'loopback': _validate_loopback_if,
                      'lsi': None,
                      'macvlan': None,
                      'mgmt-vlan': None,
                      'null': _validate_null_if,
                      'pim-decapsulator': None,
                      'pim-encapsulator': None,
                      'pppoe': None,
                      'remote-beb': None,
                      'secure-tunnel': None,
                      'software-pseudo': None,
                      'subinterface': None,
                      'tap': None,
                      'tunnel': None,
                      'tunnel-te': _validate_tunnel_te_if,
                      'virtual': None,
                      'vlan': _validate_svi_and_subif,
                      'vlan-l2': None,
                      'vpls': None,
                      'vtep': _validate_junos_vtep_if,
                      'vxlan': _validate_vxlan_if,
                      'vrf': _validate_vrf_if
                      }

    ns_dict = {
        'eos': 14,
        'junos': 12,
        'nxos': 14,
        'ospf-ibgp': 14,
        'mixed': 8,
        'vmx': 5,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)

    assert df.state.isin(['up', 'down', 'notPresent', 'notConnected',
                          'errDisabled']).all()
    # EOS uses disabled admin state on interfaces that have no XCVR
    assert df.adminState.isin(['up', 'down', 'disabled']).all()

    assert (df.type != "").all()
    assert df.type.isin(validation_fns.keys()).all()

    for iftype in validation_fns.keys():
        if validation_fns[iftype]:
            subdf = df.query(f'type == "{iftype}"').reset_index(drop=True)
            subdf_without_junos = subdf.query(
                'os.str.match("^(?:(?!junos).)*$")')
            if not subdf.empty:
                # validate interface speed without Juniper
                validate_speed_if(subdf_without_junos)
                validation_fns[iftype](subdf, df)

                assert (subdf.macaddr.str.len() == 17).all()
                assert (subdf.macaddr.str.contains(':')).all()
        assert (df.query('state != "notConnected" and type != "vpls"')
                .mtu != 0).all()

    # Juniper interfaces speed must be tested with specific function
    _validate_junos_speed_if(df.query('os.str.match("junos.*")'))
