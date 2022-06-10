from ipaddress import ip_address
import re

import pytest

import pandas as pd
from suzieq.shared.utils import validate_macaddr
from tests.conftest import validate_host_shape, DATADIR, _get_table_data


def validate_arpnd_tbl(df: pd.DataFrame):
    '''Validate the ARPND table for all values'''

    # pylint: disable=unnecessary-lambda
    assert df.ipAddress.apply(lambda x: ip_address(x)).all()
    assert (df.state.isin(["permanent", 'reachable', 'router', 'noarp',
                           'failed'])).all()
    pass_df = df.query('state != "failed"')
    assert pass_df.macaddr.apply(validate_macaddr).all()
    assert not (pass_df.oif.isin(["", "None"])).all()  # noqa
    assert (pass_df.remote.isin([True, False])).all()


def validate_interfaces(df: pd.DataFrame, datadir: str):
    '''Validate that each VRF/interface list is in interfaces table.

    This is to catch problems in parsing interfaces such that the different
    tables contain a different interface name than the interface table itself.
    For example, in parsing older NXOS, we got iftable with Eth1/1 and the
    route table with Ethernet1/1. The logic of ensuring this also ensures that
    the VRFs in the route table are all known to the interface table.
    '''

    # Create a new df of namespace/hostname/vrf to oif mapping
    only_oifs = df.groupby(by=['namespace', 'hostname'])['oif'] \
                  .unique() \
                  .reset_index() \
                  .explode('oif') \
                  .rename(columns={'oif': 'ifname'}) \
                  .reset_index(drop=True)

    # Fetch the address table
    if_df = _get_table_data('interface', datadir)
    assert not if_df.empty, 'unexpected empty interfaces table'

    if_oifs = if_df.groupby(by=['namespace', 'hostname'])['ifname'] \
                   .unique() \
                   .reset_index() \
                   .explode('ifname') \
                   .reset_index(drop=True)

    m_df = only_oifs.merge(if_oifs, how='left', indicator=True)
    # Verify we have no rows where the route table OIF has no corresponding
    # interface table info
    assert m_df.query('_merge != "both"').empty, \
        'Unknown interfaces in arpnd table'


@ pytest.mark.parsing
@ pytest.mark.arpnd
@ pytest.mark.parametrize('table', ['arpnd'])
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
def test_arpnd_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for ARPND table'''

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
    validate_arpnd_tbl(df)
    validate_interfaces(df, datadir)
