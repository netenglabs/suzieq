import pytest


import pandas as pd
from tests.conftest import validate_host_shape
from suzieq.utils import known_devtypes


def validate_device_tbl(df: pd.DataFrame):
    '''Validate the device table for all values'''

    assert (df.status.isin(['alive', 'dead'])).all()
    # assert (df.os.isin(known_devtypes())).all()
    assert (df.bootupTimestamp != 0).all()
    assert (df.vendor != '').all()
    assert (df.version != '').all()
    assert (df.model != '').all()


@ pytest.mark.parsing
@ pytest.mark.device
@ pytest.mark.parametrize('table', ['device'])
@ pytest.mark.parametrize('datadir',
                          ['tests/data/multidc/parquet-out/',
                           'tests/data/eos/parquet-out',
                           'tests/data/nxos/parquet-out',
                           'tests/data/junos/parquet-out'])
def test_device_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for device table'''

    df = get_table_data

    ns_dict = {
        'eos': 14,
        'junos': 12,
        'nxos': 14,
        'ospf-ibgp': 14,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_device_tbl(df)
