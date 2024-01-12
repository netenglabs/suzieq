from ipaddress import ip_network, ip_address

import pytest

import pandas as pd
from tests.conftest import DATADIR, validate_host_shape


def validate_igmp(df: pd.DataFrame):
    """Validate the routes table for all values"""

    assert (df.vrf != "").all()
    assert (df.group != "").all()


@pytest.mark.parsing
@pytest.mark.igmp
@pytest.mark.parametrize("table", ["igmp"])
@pytest.mark.parametrize("datadir", DATADIR)
# pylint: disable=unused-argument
def test_igmp_parsing(table, datadir, get_table_data):
    """Main workhorse routine to test parsed output for igmp"""

    df = get_table_data

    ns_dict = {
        "multicast": 2,
    }

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_igmp(df)
