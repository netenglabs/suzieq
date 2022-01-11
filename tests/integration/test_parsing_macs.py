import re

import pytest
import pandas as pd
from tests.conftest import DATADIR, validate_host_shape


def validate_macs(df: pd.DataFrame):
    '''Validate the mac table for all values'''

    assert (df.macaddr != '').all()
    assert (df.oif != '').all()
    assert (df.mackey != '').all()
    # Validate that the only MAC addresses there are fit the macaddr format
    assert df.macaddr.apply(
        lambda x: re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$",
                           x) is not None).all()
    # Ignore Linux HER entries and interface MAC entries, and some NXOS entries
    assert (df.query(
        'macaddr != "00:00:00:00:00:00" and flags != "permanent" and '
        '~oif.isin(["cpu", "sup-eth1(R)"])')
        .vlan != 0).all()
    # Remote learnt MACs MUST have a non-zero VTEP IP
    assert (df.query('flags == "remote"').remoteVtepIp != '').all()
    # Verify all entries with a remoteVtepIp have the remote flag set_index
    # Linux/CL entries also have a permanent entry representing the HER
    # pylint: disable=use-a-generator
    assert all([x in ['dynamic', 'permanent', 'static', 'remote', 'offload']
                for x in sorted(df.query('remoteVtepIp != ""')
                                ['flags'].unique())])


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

    if datadir.endswith(('vmx/parquet-out')):
        # mixed dataset has no evpn
        assert (True)
        return

    assert not df.empty
    validate_host_shape(df, ns_dict)
    validate_macs(df)
