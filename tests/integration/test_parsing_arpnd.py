from ipaddress import ip_address
import re

import pytest

import pandas as pd
from tests.conftest import validate_host_shape, DATADIR


def validate_arpnd_tbl(df: pd.DataFrame):
    '''Validate the ARPND table for all values'''

    # pylint: disable=unnecessary-lambda
    assert df.ipAddress.apply(lambda x: ip_address(x)).all()
    assert (df.state.isin(["permanent", 'reachable', 'router', 'noarp',
                           'failed'])).all()
    pass_df = df.query('state != "failed"')
    assert pass_df.macaddr.apply(
        lambda x: re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$",
                           x) is not None).all()
    assert not (pass_df.oif.isin(["", "None"])).all()  # noqa
    assert (pass_df.remote.isin([True, False])).all()


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
