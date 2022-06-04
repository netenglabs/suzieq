"""
This module contains the tests for the StaticManagerInventory class, the
one allowing to comunicate with the StaticManager in the controller side
"""
# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock

import pytest
import yaml
from cryptography.fernet import Fernet
from suzieq.poller.worker.inventory.static import StaticManagerInventory
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.shared.utils import get_random_node_list

INVENTORY_PATH = '/tmp/sq-tests-inventory'
INVENTORY_SIZE = 200


@pytest.fixture
def gen_random_inventory(tmp_path):
    """Generate a random inventory, write the files and return the resulting
    inventory, the directory containing the files and the key for credential
    decryption
    """
    inventory, credentials, result = get_random_node_list(INVENTORY_SIZE)
    # Generate the inventory files
    # Write the inventory file
    inv_data = yaml.safe_dump(inventory)
    if not inv_data:
        assert False, "Unable to produce the device list"
    with open(f'{tmp_path}/inv_0.yml', "w") as out_file:
        out_file.write(inv_data)

    # Encrypt and write the credential file
    cred_key = Fernet.generate_key()
    encryptor = Fernet(cred_key)

    cred_data = yaml.safe_dump(credentials)
    if not cred_data:
        assert False, "Unable to produce the credentials list"
    # Encrypt credential data
    enc_cred_data = encryptor.encrypt(cred_data.encode('utf-8'))
    with open(f'{tmp_path}/cred_0', "w") as out_file:
        out_file.write(enc_cred_data.decode())

    return result, tmp_path, cred_key.decode()


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
def test_not_existing_inv_file(monkeypatch):
    """Test if the inventory path is valid
    """
    monkeypatch.setenv('SQ_CONTROLLER_POLLER_CRED', 'dummy_key')
    monkeypatch.setenv('SQ_INVENTORY_PATH', 'not_existing')
    with pytest.raises(InventorySourceError, match=r'No inventory found at *'):
        StaticManagerInventory(MagicMock())


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
def test_missing_inventory_path_or_key(monkeypatch):
    """Test if an error is generated if no key for credential decryption
    or no inventory path is provided
    """
    with pytest.raises(InventorySourceError,
                       match=r'Unable to retrieve the key *'):
        StaticManagerInventory(MagicMock())

    monkeypatch.setenv('SQ_CONTROLLER_POLLER_CRED', 'dummy_key')
    with pytest.raises(InventorySourceError,
                       match='Unable to get the inventory path'):
        StaticManagerInventory(MagicMock())


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
@pytest.mark.asyncio
@pytest.mark.parametrize("n_commands", [0, 5])
async def test_static_inventory_init(monkeypatch, gen_random_inventory,
                                     n_commands):
    """Test if the static inventory is properly initialized and the device
    list is correctly received and reconstructed
    """
    expected_dict, inventory_path, key = gen_random_inventory
    monkeypatch.setenv('SQ_CONTROLLER_POLLER_CRED', key)
    monkeypatch.setenv('SQ_INVENTORY_PATH', str(inventory_path))
    if n_commands:
        monkeypatch.setenv('SQ_MAX_OUTSTANDING_CMD', str(n_commands))

    static_inv = StaticManagerInventory(MagicMock())
    # Check if the device list has been correctly obtained
    obtained_list = await static_inv._get_device_list()
    obtained_dict = {f"{o['namespace']}.{o['address']}.{o['port']}": o
                     for o in obtained_list}
    assert expected_dict == obtained_dict, 'Got unexpected device list'

    # Check if the max outstanding commands has the expected value
    assert static_inv._max_outstanding_cmd == n_commands, \
        'max_outstanding_commands has not the expected value'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
@pytest.mark.asyncio
async def test_get_device_list_wrong_key(monkeypatch, gen_random_inventory):
    """Test if the device list is correctly received and reconstructed
    """
    _, inventory_path, _ = gen_random_inventory
    monkeypatch.setenv('SQ_INVENTORY_PATH', str(inventory_path))

    # Check if we get an exception with a wrong decryption key
    wrong_key = Fernet.generate_key().decode()
    monkeypatch.setenv('SQ_CONTROLLER_POLLER_CRED', wrong_key)
    static_inv = StaticManagerInventory(MagicMock())

    with pytest.raises(InventorySourceError,
                       match=r'The credential decryption key*'):
        await static_inv._get_device_list()

    # Check if we get an exception with an invalid key
    invalid_key = 'invalid_key'
    monkeypatch.setenv('SQ_CONTROLLER_POLLER_CRED', invalid_key)
    with pytest.raises(InventorySourceError,
                       match=r'The credential decryption key*'):
        await static_inv._get_device_list()
