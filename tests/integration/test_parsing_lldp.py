import pytest


import pandas as pd
from tests.conftest import DATADIR, validate_host_shape, _get_table_data


def validate_lldp_tbl(df: pd.DataFrame):
    '''Validate the LLDP table for all values'''

    assert (df.ifname != "").all()
    assert (df.peerHostname != "").all()
    assert (df.query('subtype == "interface name"').peerIfname != "").all()
    assert (df.query('subtype == "locally assigned"').peerIfindex != "").all()
    assert (df.subtype.isin(['interface name', 'mac address',
                             'locally assigned'])).all()


def validate_interfaces(df: pd.DataFrame, datadir: str):
    '''Validate that each VRF/interface list is in interfaces table.

    This is to catch problems in parsing interfaces such that the different
    tables contain a different interface name than the interface table itself.
    For example, in parsing older NXOS, we got iftable with Eth1/1 and the
    route table with Ethernet1/1. The logic of ensuring this also ensures that
    the VRFs in the route table are all known to the interface table.
    '''

    # Fetch the address table
    if_df = _get_table_data('interface', datadir)
    assert not if_df.empty, 'unexpected empty interfaces table'

    # Create a new df of namespace/hostname/vrf to oif mapping
    only_oifs = df.groupby(by=['namespace', 'hostname'])['ifname'] \
                  .unique() \
                  .reset_index() \
                  .explode('ifname') \
                  .reset_index(drop=True)

    if_oifs = if_df.groupby(by=['namespace', 'hostname'])['ifname'] \
                   .unique() \
                   .reset_index() \
                   .explode('ifname') \
                   .reset_index(drop=True)

    m_df = only_oifs.merge(if_oifs, how='left', indicator=True)
    # Verify we have no rows where the route table OIF has no corresponding
    # interface table info
    assert m_df.query('_merge != "both"').empty, \
        'Unknown interfaces in lldp table column ifname'

    # Now test the peerIfname
    only_oifs = df.groupby(by=['namespace', 'peerHostname'])['peerIfname'] \
                  .unique() \
                  .reset_index() \
                  .explode('peerIfname') \
                  .rename(columns={'peerIfname': 'ifname',
                                   'peerHostname': 'hostname'}) \
                  .reset_index(drop=True)

    m_df = only_oifs.merge(if_oifs, how='left', indicator=True)
    # Verify we have no rows where the route table OIF has no corresponding
    # interface table info
    if not m_df.query('_merge != "both"').empty:
        # this could be because the peer host is not polled, so check that
        for row in m_df.query('_merge != "both"').itertuples():
            if not if_df.query(f'namespace == "{row.namespace}" and '
                               f'hostname == "{row.hostname}"').empty:
                assert False, \
                    'Unknown interfaces in lldp table column peerIfname'


@ pytest.mark.parsing
@ pytest.mark.lldp
@ pytest.mark.parametrize('table', ['lldp'])
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
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
    validate_interfaces(df, datadir)
