import pytest

import pandas as pd
from tests.conftest import DATADIR, validate_host_shape


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
@ pytest.mark.parametrize('datadir', DATADIR)
# pylint: disable=unused-argument
def test_device_parsing(table, datadir, get_table_data):
    '''Main workhorse routine to test parsed output for device table'''

    df = get_table_data

    ns_dict = {
        'eos': 14,
        'junos': 12,
        'nxos': 14,
        'ospf-ibgp': 14,
        'mixed': 8,
        'vmx': 5,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_device_tbl(df)
