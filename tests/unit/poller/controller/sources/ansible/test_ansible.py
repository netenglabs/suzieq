import asyncio
from typing import Dict

import pytest
from suzieq.poller.controller.source.ansible import AnsibleInventory
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.controller.utils import (get_src_sample_config,
                                                read_yaml_file)

_DATA_PATH = [
    {
        'inventory': 'tests/unit/poller/controller/sources/ansible/data/'
        'inventory/valid_inventory.json',

        'results': 'tests/unit/poller/controller/sources/ansible/data/'
        '/results/result.yaml'
    }
]
_INVALID_INVENTORY = ['tests/unit/poller/controller/sources/ansible/data/'
                      'inventory/invalid_inventory.json']

_ANSIBLE_CONFIG = get_src_sample_config('ansible')


@pytest.mark.ansible
@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.parametrize('data_path', _DATA_PATH)
@pytest.mark.asyncio
async def test_valid_inventory(data_path: Dict):
    """Test if the ansible source has been loaded correctly

    Args:
        inv_path (str): path to add in the configuration
        result_path (str): path with result to compare
    """
    config = _ANSIBLE_CONFIG
    config['path'] = data_path['inventory']

    inv = AnsibleInventory(config)

    assert inv.name == config['name']
    assert inv.namespace == config['namespace']
    assert inv.ansible_file == config['path']

    cur_inv = await asyncio.wait_for(inv.get_inventory(), 5)
    assert cur_inv == read_yaml_file(data_path['results'])


@pytest.mark.ansible
@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
def test_invalid_path():
    """Test ansible with an invalid file path
    """
    config = _ANSIBLE_CONFIG

    # wrong path
    config['path'] = 'wrong/path'

    with pytest.raises(InventorySourceError):
        AnsibleInventory(config)

    # missing 'path' field
    config.pop('path')
    with pytest.raises(InventorySourceError):
        AnsibleInventory(config)


@pytest.mark.ansible
@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.asyncio
@pytest.mark.parametrize('path', _INVALID_INVENTORY)
async def test_invalid_inventory(path: str):
    """Test invalid ansible inventory

    Args:
        path (str): invalid inventory path
    """
    config = _ANSIBLE_CONFIG
    config['path'] = path

    inv = AnsibleInventory(config)

    cur_inv = await asyncio.wait_for(inv.get_inventory(), 5)
    assert cur_inv == {}
