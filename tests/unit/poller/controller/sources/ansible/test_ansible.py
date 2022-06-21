import asyncio
from typing import Dict
from pydantic import ValidationError

import pytest
from suzieq.poller.controller.source.ansible import (AnsibleInventory,
                                                     AnsibleSourceModel)
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.shared.utils import (get_src_sample_config,
                                            read_yaml_file)

# pylint: disable=redefined-outer-name

_DATA_PATH = [
    {
        'inventory': 'tests/unit/poller/controller/sources/ansible/data/'
        'inventory/valid_inventory.json',

        'results': 'tests/unit/poller/controller/sources/ansible/data/'
        '/results/result.yaml'
    }
]
_INVALID_INVENTORY = ['tests/unit/poller/controller/sources/ansible/data/'
                      'invalid_inv/wrong_format.json']

_SKIPPING_INVENTORY = ['tests/unit/poller/controller/sources/ansible/data/'
                       'invalid_inv/skipping_devices.json']


@pytest.fixture()
def default_config() -> Dict:
    """Create a default config

    Yields:
        Dict: config
    """
    yield get_src_sample_config('ansible')


@pytest.mark.controller_source_ansible
@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('data_path', _DATA_PATH)
@pytest.mark.asyncio
async def test_valid_inventory(data_path: Dict, default_config):
    """Test if the ansible source has been loaded correctly

    Args:
        inv_path (str): path to add in the configuration
        result_path (str): path with result to compare
    """
    config = default_config
    config['path'] = data_path['inventory']

    inv = AnsibleInventory(config.copy(), validate=True)

    assert inv.name == config['name']
    assert inv._namespace == config['namespace']

    cur_inv = await asyncio.wait_for(inv.get_inventory(), 5)
    for key, item in read_yaml_file(data_path['results']).items():
        assert key in cur_inv, f'Missing expected node {key} in inventory'
        got_data = cur_inv[key]
        for k, v in item.items():
            assert k in got_data, f'Missing key {k} in for node {key}'
            assert v == got_data[k], f'Mismatch result for {k} for node {key}'


@pytest.mark.controller_source_ansible
@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
def test_invalid_path(default_config):
    """Test ansible with an invalid file path
    """
    config = default_config.copy()

    # wrong path
    config['path'] = 'wrong/path'

    with pytest.raises(ValidationError):
        AnsibleInventory(config, validate=True)

    # missing 'path' field
    config = default_config.copy()
    config.pop('path')
    with pytest.raises(ValidationError):
        AnsibleInventory(config, validate=True)


@pytest.mark.controller_source_ansible
@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.asyncio
@pytest.mark.parametrize('path', _SKIPPING_INVENTORY)
async def test_skipping_inventory(path: str, default_config):
    """Test invalid ansible inventory

    Args:
        path (str): invalid inventory path
    """
    config = default_config
    config['path'] = path

    inv = AnsibleInventory(config, validate=True)

    cur_inv = await asyncio.wait_for(inv.get_inventory(), 5)
    # the inventory is empty because all devices are skipped
    assert cur_inv == {}


@pytest.mark.controller_source_ansible
@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('path', _INVALID_INVENTORY)
def test_invalid_inventory(path: str, default_config):
    """Test invalid inventories

    Args:
        path (str): inventory file
    """
    config = default_config
    config['path'] = path

    with pytest.raises(ValidationError):
        AnsibleInventory(config, validate=True)
