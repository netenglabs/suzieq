import asyncio

import pytest
from suzieq.poller.controller.source.ansible import AnsibleInventory
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.controller.sources.utils import (get_sample_config,
                                                        read_result_data)

_RESULT_PATH = ['tests/unit/poller/controller/sources/data/ansible/results/'
                'result.yaml']

_VALID_INVENTORY = ['tests/unit/poller/controller/sources/data/ansible/'
                    'inventory/valid_inventory.json']

_INVALID_INVENTORY = ['tests/unit/poller/controller/sources/data/ansible/'
                      'inventory/invalid_inventory.json']

_ANSIBLE_CONFIG = get_sample_config('ansible')


@pytest.mark.ansible
@pytest.mark.source
@pytest.mark.parametrize('inv_path', _VALID_INVENTORY)
@pytest.mark.parametrize('result_path', _RESULT_PATH)
@pytest.mark.asyncio
async def test_valid_inventory(inv_path: str, result_path: str):
    """Test if the ansible source has been loaded correctly

    Args:
        inv_path (str): path to add in the configuration
        result_path (str): path with result to compare
    """
    config = _ANSIBLE_CONFIG
    config['path'] = inv_path

    inv = AnsibleInventory(config)

    assert inv._name == config['name']
    assert inv.namespace == config['namespace']
    assert inv.ansible_file == config['path']

    cur_inv = await asyncio.wait_for(inv.get_inventory(), 5)
    assert cur_inv == read_result_data(result_path)


@pytest.mark.ansible
@pytest.mark.source
def test_invalid_path():
    """Test ansible with an invalid file path
    """
    config = _ANSIBLE_CONFIG
    config['path'] = 'wrong/path'

    with pytest.raises(InventorySourceError):
        AnsibleInventory(config)


@pytest.mark.ansible
@pytest.mark.source
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
