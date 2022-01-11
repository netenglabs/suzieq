import pytest


import pandas as pd
import numpy as np

from tests.conftest import DATADIR, validate_host_shape


def _validate_estd_bgp_data(df: pd.DataFrame):
    '''Validate the fields in established sessions'''
    typedf = df.applymap(type)
    valid_bools = [False, True]

    assert (df.afi != '').all()
    assert (df.safi != '').all()
    assert df.afi.str.islower().all()
    assert df.safi.str.islower().all()

    assert (df.vrf != '').all()

    assert (df.updateSource != '').all()

    assert (df.peerRouterId != '').all()

    assert (df.peerAsn != 0).all()

    assert df.advertiseAllVnis.isin(valid_bools).all()
    assert df.nhUnchanged.isin(valid_bools).all()
    assert df.nhSelf.isin([True, False]).all()
    assert df.defOriginate.isin(valid_bools).all()
    assert df.softReconfig.isin(valid_bools).all()

    assert df.bfdStatus.isin(['up', 'down', 'disabled']).all()

    assert (typedf.afisAdvOnly == np.ndarray).all()
    assert (typedf.afisRcvOnly == np.ndarray).all()
    assert all(x in ["['standard' 'extended']", '[]', "['standard']"]
               for x in df.communityTypes.astype(str).unique())

    if not df.query('pfxRx == 0').empty:
        print(df.query('pfxRx == 0'))
    if not df.query('pfxTx == 0').empty:
        print(df.query('pfxRx == 0'))

    assert(df.keepaliveTime != 0).all()
    assert (df.estdTime != 0).all()


def _validate_notestd_bgp_data(df: pd.DataFrame):
    '''Validate the fields in established sessions'''
    assert(df.query('~os.str.contains("junos")').keepaliveTime != 0).all()


def validate_bgp_data(df: pd.DataFrame):
    '''Validate the dataframe for all BGP values'''

    # First validate that all entries have a state thats known
    assert (df.state.isin(['Established', 'NotEstd', 'dynamic'])).all()
    assert (df.peer != '').all() and (df.peer.str.lower() != 'none').all()
    assert (df.query('namespace != "nsdevlab"').routerId != '').all()
    assert (df.asn != 0).all()

    assert (df.query('state != "dynamic"').holdTime != 0).all()

    estd_df = df.query('state == "Established"').reset_index(drop=True)
    notestd_df = df.query('state == "NotEstd"').reset_index(drop=True)

    _validate_notestd_bgp_data(notestd_df)
    _validate_estd_bgp_data(estd_df)


@ pytest.mark.parsing
@ pytest.mark.bgp
@pytest.mark.parametrize('table', ['bgp'])
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
def test_bgp_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for BGP'''

    df = get_table_data

    ns_dict = {
        'eos': 10,
        'junos': 8,
        'nxos': 10,
        'ospf-ibgp': 10,
        'mixed': 0,
        'vmx': 3,
    }

    if datadir.endswith('mixed/parquet-out'):
        # mixed dataset has no BGP
        assert (True)
        return

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_bgp_data(df)
