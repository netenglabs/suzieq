import asyncio
from typing import Dict

import pytest
from suzieq.poller.controller.source.ansible import AnsibleInventory
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

    inv = AnsibleInventory(config)

    assert inv.name == config['name']
    assert inv.namespace == config['namespace']
    assert inv.ansible_file == config['path']

    cur_inv = await asyncio.wait_for(inv.get_inventory(), 5)
    assert cur_inv == read_yaml_file(data_path['results'])


@pytest.mark.controller_source_ansible
@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
def test_invalid_path(default_config):
    """Test ansible with an invalid file path
    """
    config = default_config

    # wrong path
    config['path'] = 'wrong/path'

    with pytest.raises(InventorySourceError):
        AnsibleInventory(config)

    # missing 'path' field
    config.pop('path')
    with pytest.raises(InventorySourceError):
        AnsibleInventory(config)


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

    inv = AnsibleInventory(config)

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

    with pytest.raises(InventorySourceError):
        AnsibleInventory(config)
