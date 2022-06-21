import re

import pytest
import numpy as np
import pandas as pd
from suzieq.shared.utils import validate_macaddr
from tests.conftest import DATADIR, validate_host_shape, _get_table_data


def validate_macs(df: pd.DataFrame):
    '''Validate the mac table for all values'''

    assert (df.macaddr != '').all()
    assert (df.oif != '').all()
    assert (df.mackey != '').all()
    # Validate that the only MAC addresses there are fit the macaddr format
    assert df.macaddr.apply(validate_macaddr).all()
    # Ignore Linux HER entries and interface MAC entries, and some NXOS entries
    assert (df.query(
        'macaddr != "00:00:00:00:00:00" and flags != "permanent" and '
        '~(oif.isin(["cpu", "sup-eth1", "sup-eth1(R)"]) or flags == "router")')
        .vlan != 0).all()
    # Remote learnt MACs MUST have a non-zero VTEP IP
    assert (df.query('flags == "remote"').remoteVtepIp != '').all()
    # Verify all entries with a remoteVtepIp have the remote flag set_index
    # Linux/CL entries also have a permanent entry representing the HER
    # pylint: disable=use-a-generator
    assert all([x in ['dynamic', 'permanent', 'static', 'remote', 'offload']
                for x in sorted(df.query('remoteVtepIp != ""')
                                ['flags'].unique())])


def validate_interfaces(df: pd.DataFrame, datadir: str):
    '''Validate that each VLAN/interface list is in interfaces table.

    This is to catch problems in parsing interfaces such that the different
    tables contain a different interface name than face table itself.
    For example, in parsing older NXOS, we got iftable with Eth1/1 and the
    mac table with Ethernet1/1. The logic of ensuring this also ensures that
    the VLAN table is also validated as need to access it for trunk ports.
    '''

    # Create a new df of namespace/hostname/vrf to oif mapping
    # exclude interfaces such as cpu/sup-eth1/vtep.* etc. as well
    # as routed interfaces that have a VLAN of 0
    only_oifs = df.query('~oif.isin(["bridge", "sup-eth1", '
                         '"vPC Peer-Link", "nve1", "Router"])') \
                  .query('~oif.str.startswith("vtep.")') \
                  .query('vlan != 0') \
                  .groupby(by=['namespace', 'hostname', 'vlan'])['oif'] \
                  .unique() \
                  .reset_index() \
                  .explode('oif') \
                  .rename(columns={'oif': 'ifname'}) \
                  .reset_index(drop=True) \

    # Fetch the address table
    if_df = _get_table_data('interface', datadir) \
        .explode('vlanList') \
        .reset_index(drop=True)

    assert not if_df.empty, 'unexpected empty interfaces table'

    if_df['vlan'] = np.where(~if_df.vlanList.isnull(), if_df.vlanList,
                             if_df.vlan)

    if_oifs = if_df[['namespace', 'hostname', 'vlan', 'ifname']] \
        .groupby(by=['namespace', 'hostname', 'vlan'])['ifname'] \
        .unique() \
        .reset_index() \
        .explode('ifname') \
        .reset_index(drop=True)

    merge_df = only_oifs.merge(if_oifs, how='left', indicator=True)
    # Verify we have no rows where the route table OIF has no corresponding
    # interface table info
    assert merge_df.query('_merge != "both"').empty, \
        'unknown interfaces in mac table'


@ pytest.mark.parsing
@ pytest.mark.mac
@ pytest.mark.parametrize('table', ['macs'])
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
def test_macs_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for MAC table'''

    df = get_table_data

    ns_dict = {
        'eos': 11,
        'junos': 7,
        'nxos': 13,
        'ospf-ibgp': 7,
        'mixed': 2,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_macs(df)
    validate_interfaces(df, datadir)
