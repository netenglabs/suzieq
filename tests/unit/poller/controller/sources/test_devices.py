import asyncio
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
from suzieq.poller.controller.source.base_source import Source
from suzieq.shared.exceptions import InventorySourceError

# pylint: disable=protected-access

_INVENTORY = [{
    'native-ns.192.168.123.123.443':
    {
        'address': '192.168.123.123',
        'hostname': None,
        'namespace': 'native-ns',
        'port': 443,
        'transport': 'http'
    },
    'native-ns.192.168.123.164.443':
    {
        'address': '192.168.123.164',
        'devtype': 'eos',
        'hostname': None,
        'namespace': 'native-ns',
        'port': 443,
        'ignore_known_hosts': False
    }
}]


def set_inventory_mock(self, inventory: Dict):
    """This mock overrides the Source.set_inventory

    This function remove some validation which is not needed for this test

    Args:
        inventory (Dict): inventory to be set
    """
    self.set_device(inventory)
    self._inventory = inventory
    if not self._inv_is_set:
        self._inv_is_set = True
        self._inv_is_set_event.set()


@pytest.mark.controller_device
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.asyncio
@pytest.mark.parametrize('inventory', _INVENTORY)
async def test_devices_set(inventory: Dict):
    """Test devices are correctly set

    Args:
        inventory (Dict): inventory to be loaded
    """
    config = {
        'device': {
            'ignore-known-hosts': True,
            'jump-host': None,
            'jump-host-key-file': None,
            'devtype': 'panos',
            'transport': 'ssh',

        }
    }

    with patch.multiple(Source, _load=MagicMock(),
                        set_inventory=set_inventory_mock):
        src = Source(config)
        assert src._device == config['device']

        src.set_inventory(inventory)
        inv = await asyncio.wait_for(src.get_inventory(), 5)

        # emulate what the function Source.set_device should do
        exp_inv = {}
        for key, node in inventory.items():
            exp_inv[key] = node.copy()
            for k, v in config['device'].items():
                k = k.replace('-', '_')
                if k not in exp_inv[key]:
                    exp_inv[key][k] = v

        assert inv == exp_inv


@pytest.mark.controller_device
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
def test_wrong_device_config():
    """Test device wrong configuration
    """
    config = {
        'device': {
            'wrong': 'parameter'
        }
    }

    with pytest.raises(InventorySourceError):
        Source(config)
