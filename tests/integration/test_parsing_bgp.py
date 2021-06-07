import pytest


import pandas as pd
import numpy as np

from tests.conftest import create_dummy_config_file
from suzieq.sqobjects import get_sqobject


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
    assert(df.query('namespace != "junos"').keepaliveTime != 0).all()


def validate_bgp_data(df: pd.DataFrame):
    '''Validate the dataframe for all BGP values'''

    # First validate that all entries have a state that's either Established or NotEstd
    df.state.isin(['Established', 'NotEstd']).all()
    assert (df.peer != '').all() and (df.peer.str.lower() != 'none').all()
    assert (df.query('namespace != "nsdevlab"').routerId != '').all()
    assert (df.asn != 0).all()

    assert (df.holdTime != 0).all()

    estd_df = df.query('state == "Established"').reset_index(drop=True)
    notestd_df = df.query('state != "Established"').reset_index(drop=True)

    _validate_notestd_bgp_data(notestd_df)
    _validate_estd_bgp_data(estd_df)


@ pytest.mark.parsing
@ pytest.mark.bgp
@ pytest.mark.parametrize('datadir',
                          ['tests/data/multidc/parquet-out/',
                           'tests/data/eos/parquet-out',
                           'tests/data/nxos/parquet-out',
                           'tests/data/junos/parquet-out'])
def test_bgp_parsing(datadir):
    '''Main workhorse routine to test parsed output for BGP'''

    cfgfile = create_dummy_config_file(datadir=datadir)

    df = get_sqobject('bgp')(config_file=cfgfile).get(columns=['*'])
    device_df = get_sqobject('device')(config_file=cfgfile) \
        .get(columns=['namespace', 'hostname', 'os'])

    if not device_df.empty:
        df = df.merge(device_df, on=['namespace', 'hostname']) \
               .fillna({'os': ''})

    assert not df.empty
    validate_bgp_data(df)
