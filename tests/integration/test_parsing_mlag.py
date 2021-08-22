import pytest

import re
from ipaddress import ip_address
import pandas as pd
from tests.conftest import validate_host_shape


def validate_mlag_tbl(df: pd.DataFrame):
    '''Validate the MLAG table for all values'''

    assert (df.state.isin(['active', 'disabled', 'inactive'])).all()
    assert (df.role != '').all()
    assert df.peerAddress.apply(lambda x: ip_address(x)).all()
    assert (df.peerLink != '').all()
    assert (df.query('backupActive == True').backupIP != '').all()
    assert df.peerMacAddress.apply(
        lambda x: re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$",
                           x) is not None).all()
    assert df.systemId.apply(
        lambda x: re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$",
                           x) is not None).all()

    assert (df.mlagDualPortsCnt == df.mlagDualPortsList.str.len()).all()
    assert (df.mlagSinglePortsCnt == df.mlagSinglePortsList.str.len()).all()
    assert (df.mlagErrorPortsCnt == df.mlagErrorPortsList.str.len()).all()

    noncl_df = df.query('os != "cumulus"')
    assert (noncl_df.configSanity.isin(['consistent', 'inconsistent'])).all()
    assert (noncl_df.domainId != '').all()
    assert (noncl_df.usesLinkLocal == False).all()
    assert (noncl_df.peerLinkStatus.isin(['up', 'down'])).all()


@ pytest.mark.parsing
@ pytest.mark.mlag
@ pytest.mark.parametrize('table', ['mlag'])
@ pytest.mark.parametrize('datadir',
                          ['tests/data/multidc/parquet-out/',
                           'tests/data/eos/parquet-out',
                           'tests/data/nxos/parquet-out',
                           ])
def test_mlag_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for MLAG table'''

    df = get_table_data

    ns_dict = {
        'eos': 4,
        'junos': 4,
        'nxos': 4,
        'ospf-ibgp': 4,
    }

    if datadir.endswith(('mixed/parquet-out', 'vmx/parquet-out')):
        assert(True)
        return
    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_mlag_tbl(df)
