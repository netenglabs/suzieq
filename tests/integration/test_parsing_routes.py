import pytest


import pandas as pd
from ipaddress import ip_network, ip_address

from tests.conftest import validate_host_shape


def validate_routes(df: pd.DataFrame):
    '''Validate the routes table for all values'''

    assert (df.vrf != '').all()
    assert (df.prefix != '').all()
    assert (df.action.isin(
        ['multirecv', 'local', 'forward', 'drop', 'reject'])).all()
    # For all forward action, there has to be an outgoimg interface or nexthop OP
    assert (df.ipvers.isin([4, 6])).all()

    for row in df.itertuples():
        assert ip_network(row.prefix)
        assert ((row != "forward") or ((row.action == "forward") and
                                       ((row.nexthopIps != []).all() or
                                        (row.oifs != []).all())))
        assert ((row.os == "linux") or ((row.os == "cumulus" and
                                         row.hostname == "internet" and
                                         row.prefix == "0.0.0.0/0")) or
                ((row.os != "linux") and (row.protocol != "")))
        if row.nexthopIps != []:
            assert ([ip_address(x) for x in row.nexthopIps])

    noncl_data = df.query(
        'os != "linux" and os != "cumulus" and not protocol.isin(["direct", "local", "connected"])')
    assert (noncl_data.query('nexthopIps.str.len() != 0').preference != 0).all()

    # The OS that supply route uptime
    upt_df = df.query('not os.isin(["linux", "cumulus", "EOS", "eos"])')
    assert (upt_df.statusChangeTimestamp != 0).all()


@ pytest.mark.parsing
@ pytest.mark.route
@ pytest.mark.parametrize('table', ['routes'])
@ pytest.mark.parametrize('datadir',
                          ['tests/data/multidc/parquet-out/',
                           'tests/data/eos/parquet-out',
                           'tests/data/nxos/parquet-out',
                           'tests/data/junos/parquet-out'])
def test_routes_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for Routes'''

    df = get_table_data

    ns_dict = {
        'eos': 14,
        'junos': 12,
        'nxos': 14,
        'ospf-ibgp': 14,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_routes(df)
