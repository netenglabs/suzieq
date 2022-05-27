import pytest
import pandas as pd

from tests.conftest import DATADIR, validate_host_shape, _get_table_data
from tests.integration.utils import validate_vrfs


def _validate_estd_ospf_data(df: pd.DataFrame):
    '''Validate data for those sessions that are in neighbor output'''

    valid_bools = [False, True]

    assert (df.areaStub.isin(valid_bools)).all()
    assert (df.adjState.isin(['full', 'passive'])).all()
    assert (df.ifState.isin(["up", "down", "adminDown"])).all()
    assert (df.ipAddress.str.contains('/')).all()

    npsv_df = df.query('adjState != "passive"')
    if not npsv_df.empty:
        assert (npsv_df.peerIP != '').all()
        # assert (npsv_df.peerHostname != '').all()
        assert (npsv_df.peerRouterId != '').all()
        assert (npsv_df.nbrCount != 0).all()
        assert (npsv_df.bfdStatus.isin(['unknown', 'disabled',
                                        'up', 'down'])).all()


def _validate_notestd_ospf_data(df: pd.DataFrame):
    '''Validate data for those sessions not in neighbor output'''
    # Commenting out this check because in some cases, this can happen as in
    # when we captured the ospf output for mixed namespace. Due to the way
    # the commands are captured, its possible to get ospfIf with one adjacent
    # neighbor while the ospfnbr output for that interface is still blank. So
    # commenting out this check.
    # assert (df.nbrCount == 0).all()
    assert (df.ipAddress.str.contains('/')).all()


def _validate_common_ospf_data(df: pd.DataFrame):
    '''Validate stuff common to all BGP sessions'''

    assert not df.empty

    assert (df.area != '').all()
    assert (df.routerId != '').all()

    nocls_df = df.query('~os.isin(["cumulus", "sonic"])')
    assert (nocls_df.ipAddress != '').all()

    # Timers
    assert (df.deadTime != 0).all()
    assert (df.retxTime != 0).all()
    assert (df.helloTime != 0).all()

    assert (df.networkType.isin(['p2p', 'broadcast', 'loopback'])).all()


def validate_interfaces(df: pd.DataFrame, datadir: str):
    '''Validate that each interface list is in interfaces table.

    This is to catch problems in parsing interfaces such that the different
    tables contain a different interface name than the interface table itself.
    For example, in parsing older NXOS, we got iftable with Eth1/1 and the
    route table with Ethernet1/1. The logic of ensuring this also ensures that
    the VRFs in the route table are all known to the interface table.
    '''

    # Create a new df of namespace/hostname/vrf to oif mapping
    only_oifs = df.groupby(by=['namespace', 'hostname'])['ifname'] \
                  .unique() \
                  .reset_index() \
                  .explode('ifname') \
                  .reset_index(drop=True)

    # Fetch the address table
    if_df = _get_table_data('interface', datadir)
    assert not if_df.empty, 'unexpected empty interfaces table'

    addr_oifs = if_df.groupby(by=['namespace', 'hostname'])['ifname'] \
                     .unique() \
                     .reset_index() \
                     .explode('ifname') \
                     .reset_index(drop=True)

    m_df = only_oifs.merge(addr_oifs, how='left', indicator=True)
    # Verify we have no rows where the route table OIF has no corresponding
    # interface table info
    assert m_df.query('_merge != "both"').empty, \
        'Unknown interfaces in ospf table'


@ pytest.mark.parsing
@ pytest.mark.ospf
@ pytest.mark.parametrize('table', ['ospf'])
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
def test_ospf_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for OSPF'''

    if 'basic_dual_bgp' in datadir:
        # No OSPF in this datadir
        return

    df = get_table_data

    ns_dict = {
        'eos': 8,
        'junos': 6,
        'nxos': 8,
        'ospf-ibgp': 8,
        'mixed': 8
    }

    validate_host_shape(df, ns_dict)
    # These apply to all sessions
    _validate_common_ospf_data(df)

    estd_df = df.query('adjState.isin(["full", "passive"])').reset_index()
    notestd_df = df.query(
        'not adjState.isin(["full", "passive"])').reset_index()

    _validate_notestd_ospf_data(notestd_df)
    _validate_estd_ospf_data(estd_df)
    validate_interfaces(df, datadir)
    validate_vrfs(df, 'ospf', datadir)
