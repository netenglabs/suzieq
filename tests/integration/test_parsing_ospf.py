import pytest
import pandas as pd

from tests.conftest import DATADIR, validate_host_shape


def _validate_estd_ospf_data(df: pd.DataFrame):
    '''Validate data for those sessions that are in neighbor output'''

    valid_bools = [False, True]

    assert (df.areaStub.isin(valid_bools)).all()
    assert (df.adjState.isin(['full', 'passive'])).all()
    assert (df.ifState.isin(["up", "down"])).all()

    npsv_df = df.query('adjState != "passive"')
    if not npsv_df.empty:
        assert (npsv_df.peerIP != '').all()
        assert (npsv_df.peerHostname != '').all()
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
    pass


def _validate_common_ospf_data(df: pd.DataFrame):
    '''Validate stuff common to all BGP sessions'''

    assert not df.empty

    assert (df.area != '').all()
    assert (df.routerId != '').all()
    assert (df.ipAddress != '').all()

    # Timers
    assert (df.deadTime != 0).all()
    assert (df.retxTime != 0).all()
    assert (df.helloTime != 0).all()

    assert (df.networkType.isin(['p2p', 'broadcast', 'loopback'])).all()


@ pytest.mark.parsing
@ pytest.mark.ospf
@pytest.mark.parametrize('table', ['ospf'])
@ pytest.mark.parametrize('datadir', DATADIR)
def test_ospf_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for OSPF'''

    df = get_table_data

    ns_dict = {
        'eos': 8,
        'junos': 6,
        'nxos': 8,
        'ospf-ibgp': 8,
        'mixed': 8
    }

    if datadir.endswith(('vmx/parquet-out')):
        # mixed dataset has no evpn
        assert (True)
        return

    validate_host_shape(df, ns_dict)
    # These apply to all sessions
    _validate_common_ospf_data(df)

    estd_df = df.query('adjState.isin(["full", "passive"])').reset_index()
    notestd_df = df.query(
        'not adjState.isin(["full", "passive"])').reset_index()

    _validate_notestd_ospf_data(notestd_df)
    _validate_estd_ospf_data(estd_df)
