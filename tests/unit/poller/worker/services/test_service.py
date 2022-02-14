import os
from copy import deepcopy

import numpy as np
import pytest
from suzieq.poller.worker.services.service import Service
from suzieq.shared.schema import Schema, SchemaForTable
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file
from tests.unit.poller.worker.services.dummy_out import interface_out

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="session")
def old_out():
    """Get an example of old output
    """
    return interface_out


@pytest.fixture
def service_for_diff():
    """Init the service for testing the get_diff() function
    """
    cfg_file = create_dummy_config_file()
    cfg = load_sq_config(cfg_file)
    # Build the shema
    schema_dir = cfg['schema-directory']
    schema = Schema(schema_dir)
    schema_tab = SchemaForTable('interfaces', schema)
    # Initialize only the fields we need for testing purposes
    keys = ['namespace', 'hostname', 'ifname']
    service = Service('interfaces', None, 15, 'state', keys, [],
                      schema_tab, None, None, 'forever')
    yield service
    os.remove(cfg_file)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_equal(old_out, service_for_diff):
    """Test the comparison between two equal chunks
    """

    adds, dels = service_for_diff.get_diff(old_out, old_out)
    assert not adds, 'Expected no additions comparing the same chunks'
    assert not dels, 'Expected no deletions comparing the same chunks'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_different(old_out, service_for_diff):
    """Test the comparison between different chunks
    """
    new_out = deepcopy(old_out)
    # Change the ifname of a record, expected an adds and a del
    new_out[0]['ifname'] = 'eth12'
    # Change the address list in one of the records
    new_out[1]['ipAddressList'] = np.array(['10.0.0.12/24'])
    adds, dels = service_for_diff.get_diff(old_out, new_out)
    assert len(adds) == 2, f'Expected 2 adds but got {len(adds)}'
    assert new_out[0] in adds
    assert new_out[1] in adds
    assert len(dels) == 1, f'Expected 1 del but got {len(dels)}'
    assert old_out[0] in dels


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_different_collections_order(old_out, service_for_diff):
    """Test that in comparison different order in collections is ignored
    """
    new_out = deepcopy(old_out)
    new_out[1]['ipAddressList'] = np.array(['192.168.16.1/24', '10.0.0.1/24'])
    adds, dels = service_for_diff.get_diff(old_out, new_out)
    assert not adds, 'Returned adds, but only different collection order'
    assert not dels, 'Returned dels, but only different collection order'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_field_out_of_schema(old_out, service_for_diff):
    """Test that fields out of the schema are ignored in comparison
    """
    new_out = deepcopy(old_out)
    # Add a dummy field in all the dict of new_out
    out_of_schema_fields = {
        'value1_temp': 'temp1',
        'value2_temp': 'temp2',
        'value3_temp': 'temp3'
    }
    for n in new_out:
        n.update(out_of_schema_fields)

    adds, dels = service_for_diff.get_diff(old_out, new_out)

    assert not adds, 'Returned adds, but only added fields out of schema'
    assert not dels, 'Returned dels, but only added fields out of schema'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
def test_diff_ignored_fields(old_out, service_for_diff):
    """Test that fields out of the schema are ignored in comparison
    """
    new_out = deepcopy(old_out)
    ignored_adds = {
        'ip6AddressList': np.array(['fe80::16/24'])
    }
    for n in new_out:
        n.update(ignored_adds)

    service_for_diff.ignore_fields = ['ip6AddressList']
    adds, dels = service_for_diff.get_diff(old_out, new_out)

    assert not adds, 'Returned adds, but only added a field in ignore list'
    assert not dels, 'Returned dels, but only added a field in ignore list'
