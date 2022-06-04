from ipaddress import ip_network, ip_address

import pytest

import pandas as pd
from tests.conftest import DATADIR, validate_host_shape, _get_table_data
from tests.integration.utils import validate_vrfs


def validate_routes(df: pd.DataFrame):
    '''Validate the routes table for all values'''

    assert (df.vrf != '').all()
    assert (df.prefix != '').all()
    assert (df.action.isin(
        ['multirecv', 'local', 'forward', 'drop', 'reject', 'inactive'])).all()
    # For all forward action, there has to be an outgoimg interface
    # or nexthop OP
    assert (df.ipvers.isin([4, 6])).all()

    for row in df.itertuples():
        assert ip_network(row.prefix, strict=False)
        assert ((row != "forward") or ((row.action == "forward") and
                                       ((row.nexthopIps != []).all() or
                                        (row.oifs != []).all())))
        assert ((row.os in ["linux", "sonic"]) or
                ((row.os == "cumulus" and
                  row.hostname == "internet" and
                  row.prefix == "0.0.0.0/0")) or
                ((row.os != "linux") and (row.protocol != "")))
        if row.nexthopIps.any():
            assert ([ip_address(x) for x in row.nexthopIps])

    noncl_data = df.query(
        '~os.isin(["linux", "cumulus"]) and '
        '(os == "ioxe" and protocol != "static") and'
        '~protocol.isin(["direct", "local", "connected"])')
    assert (noncl_data.query(
        'nexthopIps.str.len() != 0 and protocol != "hsrp" and '
        'namespace != "panos" and hostname != "firewall01" ')
        .preference != 0).all()

    # The OS that supply route uptime
    upt_df = df.query('not os.isin(["linux", "sonic", "cumulus", "eos"]) and '
                      'not protocol.isin(["local", "connected", "static"])')
    assert (upt_df.statusChangeTimestamp != 0).all()


def validate_interfaces(df: pd.DataFrame, datadir: str):
    '''Validate that each VRF/interface list is in interfaces table.

    This is to catch problems in parsing interfaces such that the different
    tables contain a different interface name than the interface table itself.
    For example, in parsing older NXOS, we got iftable with Eth1/1 and the
    route table with Ethernet1/1. The logic of ensuring this also ensures that
    the VRFs in the route table are all known to the interface table.
    '''

    # Create a new df of namespace/hostname/vrf to oif mapping
    only_oifs = df[['namespace', 'hostname', 'vrf', 'oifs']] \
        .query('vrf != ":vxlan"') \
        .explode('oifs') \
        .dropna() \
        .groupby(by=['namespace', 'hostname', 'vrf'])['oifs'] \
        .unique() \
        .reset_index() \
        .explode('oifs') \
        .query('~oifs.str.contains("_nexthopVrf:")') \
        .rename(columns={'oif': 'ifname'}) \
        .reset_index(drop=True)

    # Fetch the address table
    addr_df = _get_table_data('address', DATADIR[0])
    assert not addr_df.empty, 'unexpected empty address table'

    addr_oifs = addr_df[['namespace', 'hostname', 'vrf', 'ifname']] \
        .groupby(by=['namespace', 'hostname', 'vrf'])['ifname'] \
        .unique() \
        .reset_index() \
        .explode('ifname') \
        .reset_index(drop=True)

    m_df = only_oifs.merge(addr_oifs, how='left', indicator=True)
    # Verify we have no rows where the route table OIF has no corresponding
    # interface table info
    assert m_df.query('_merge != "both" and namespace != "vmx"').empty, \
        'Unknown interfaces in routes table'


@ pytest.mark.parsing
@ pytest.mark.route
@ pytest.mark.parametrize('table', ['routes'])
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
def test_routes_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for Routes'''

    df = get_table_data

    ns_dict = {
        'eos': 14,
        'junos': 12,
        'nxos': 14,
        'ospf-ibgp': 14,
        'vmx': 5,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_routes(df)
    validate_interfaces(df, datadir)
    validate_vrfs(df, 'routes', datadir)
