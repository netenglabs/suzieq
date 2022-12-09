import os
import tempfile
from copy import deepcopy
from shutil import rmtree
from time import time
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from suzieq.db.parquet.parquetdb import SqParquetDB
from suzieq.poller.worker.services.service import Service
from suzieq.shared.schema import Schema, SchemaForTable
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file
from tests.unit.poller.worker.services.dummy_out import interface_out

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="session")
def device_out():
    """Get an example of old output
    """
    return interface_out


@pytest.fixture
def service_for_diff():
    """Init the service for testing the get_diff() function
    """
    data_dir = tempfile.mkdtemp()
    cfg_file = create_dummy_config_file(datadir=data_dir)
    cfg = load_sq_config(config_file=cfg_file)
    # Build the shema
    schema_dir = cfg['schema-directory']
    schema = Schema(schema_dir)
    schema_tab = SchemaForTable('interfaces', schema)
    db_access = SqParquetDB(cfg, None)
    # Initialize only the fields we need for testing purposes
    keys = ['namespace', 'hostname', 'ifname']
    service = Service('interfaces', None, 15, 'state', keys, [],
                      schema_tab, None, db_access, 'forever')
    yield service
    os.remove(cfg_file)
    rmtree(data_dir)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_equal(device_out, service_for_diff):
    """Test the comparison between two equal chunks
    """

    adds, dels = service_for_diff.get_diff(device_out, device_out,
                                           add_all=False)
    assert not adds, 'Expected no additions comparing the same chunks'
    assert not dels, 'Expected no deletions comparing the same chunks'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_different(device_out, service_for_diff):
    """Test the comparison between different chunks
    """
    new_out = deepcopy(device_out)
    # Change the ifname of a record, expected an adds and a del
    new_out[0]['ifname'] = 'eth12'
    # Change the address list in one of the records
    new_out[1]['ipAddressList'] = np.array(['10.0.0.12/24'])
    adds, dels = service_for_diff.get_diff(device_out, new_out, add_all=False)
    assert len(adds) == 2, f'Expected 2 adds but got {len(adds)}'
    assert new_out[0] in adds
    assert new_out[1] in adds
    assert len(dels) == 1, f'Expected 1 del but got {len(dels)}'
    assert device_out[0] in dels


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_different_collections_order(device_out, service_for_diff):
    """Test that in comparison different order in collections is ignored
    """
    new_out = deepcopy(device_out)
    new_out[1]['ipAddressList'] = np.array(['192.168.16.1/24', '10.0.0.1/24'])
    adds, dels = service_for_diff.get_diff(device_out, new_out, add_all=False)
    assert not adds, 'Returned adds, but only different collection order'
    assert not dels, 'Returned dels, but only different collection order'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_field_out_of_schema(device_out, service_for_diff):
    """Test that fields out of the schema are ignored in comparison
    """
    new_out = deepcopy(device_out)
    # Add a dummy field in all the dict of new_out
    out_of_schema_fields = {
        'value1_temp': 'temp1',
        'value2_temp': 'temp2',
        'value3_temp': 'temp3'
    }
    for n in new_out:
        n.update(out_of_schema_fields)

    adds, dels = service_for_diff.get_diff(device_out, new_out, add_all=False)

    assert not adds, 'Returned adds, but only added fields out of schema'
    assert not dels, 'Returned dels, but only added fields out of schema'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_ignored_fields(device_out, service_for_diff):
    """Test that fields out of the schema are ignored in comparison
    """
    new_out = deepcopy(device_out)
    ignored_adds = {
        'ip6AddressList': np.array(['fe80::16/24'])
    }
    for n in new_out:
        n.update(ignored_adds)

    service_for_diff.ignore_fields = ['ip6AddressList']
    adds, dels = service_for_diff.get_diff(device_out, new_out, add_all=False)

    assert not adds, 'Returned adds, but only added a field in ignore list'
    assert not dels, 'Returned dels, but only added a field in ignore list'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.asyncio
async def test_write_device_on_reboot(service_for_diff: Service, device_out):
    """Test whether the service is able to detect node reboots
    """
    out_df = pd.DataFrame(device_out)
    out_df['sqvers'] = out_df['sqvers'].astype(str)

    db_access = service_for_diff._db_access
    db_access.write('interfaces', 'pandas', out_df,
                    False, service_for_diff.schema, None)

    boot_ts = out_df['deviceSession'].iloc[0]
    service_for_diff._post_work_to_writer = Mock()
    ##
    # 1. Test whether the service write if there is a small difference in time
    ##
    service_for_diff._node_boot_timestamps = {}  # reset boot cache
    device_boot = boot_ts + 10
    await service_for_diff.commit_data(
        device_out, 'vagrant', 'leaf01', device_boot)
    try:
        service_for_diff._post_work_to_writer.assert_not_called()
    except AssertionError:
        pytest.fail('The poller wrote with no changes and 10s as difference '
                    'in boot timestamp')

    ##
    # 2. Test whether the service writes all if the device reboots
    ##
    service_for_diff._node_boot_timestamps = {}  # reset boot cache
    device_boot = boot_ts + 40000
    await service_for_diff.commit_data(
        device_out, 'vagrant', 'leaf01', device_boot)
    try:
        service_for_diff._post_work_to_writer.assert_called_once()
    except AssertionError:
        pytest.fail('The poller didn\'t write after a reboot')

    written_records = service_for_diff._post_work_to_writer.call_args[0][0]
    assert len(written_records) == len(device_out), \
        'Not all the records written'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.asyncio
async def test_write_device_on_reboot_no_prev_session(
        service_for_diff: Service, device_out):
    """The whether the poller writes without issues even if there is not data
    about previous device sessions
    """
    out_df = pd.DataFrame(device_out)
    out_df['sqvers'] = out_df['sqvers'].astype(str)
    out_df['deviceSession'] = None

    db_access = service_for_diff._db_access
    db_access.read = Mock(return_value=out_df)

    service_for_diff._post_work_to_writer = Mock()
    service_for_diff._node_boot_timestamps = {}  # reset boot cache

    await service_for_diff.commit_data(
        device_out, 'vagrant', 'leaf01', time())
    try:
        service_for_diff._post_work_to_writer.assert_called_once()
    except AssertionError:
        pytest.fail('The poller didn\'t write with missing prev reboot data')

    written_records = service_for_diff._post_work_to_writer.call_args[0][0]
    assert len(written_records) == len(device_out), \
        'Not all the records written'
