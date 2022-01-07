"""
This module contains the tests for the StaticManagerInventory class, the
one allowing to comunicate with the StaticManager in the controller side
"""
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import random
import shutil
from unittest.mock import MagicMock

from pathlib import Path
import pytest
import yaml
from cryptography.fernet import Fernet
from faker import Faker
from suzieq.poller.worker.inventory.static import StaticManagerInventory
from suzieq.shared.exceptions import InventorySourceError

INVENTORY_PATH = '/tmp/sq-tests-inventory'
INVENTORY_SIZE = 200


@pytest.fixture
def gen_random_inventory():
    """Generate a random inventory, write the files and return the resulting
    inventory, the directory containing the files and the key for credential
    decryption
    """
    inventory = {}
    credentials = {}
    result = {}

    fake = Faker()
    Faker.seed(random.randint(1, 10000))

    ports = [22, 443, 1244, 8080, 4565]
    transports = ['ssh', 'https', 'http']
    devtypes = ['panos', 'eos', None]
    namespaces = ['data-center-north', 'south-data-center']
    keys = ['tests/unit/poller/worker/utils/sample_key', None]
    for _ in range(INVENTORY_SIZE):
        entry = {
            'address': fake.ipv4(address_class='c'),
            'username': fake.domain_word(),
            'port': fake.word(ports),
            'transport': fake.word(transports),
            'devtype': fake.word(devtypes),
            'namespace': fake.word(namespaces),
            'jump_host': fake.word([f"// {fake.domain_word()}@{fake.ipv4()}",
                                   None])
        }

        cred = {
            'password': fake.password(),
            'ssh_keyfile': fake.word(keys),
            'jump_host_key_file': fake.word(keys),
            'passphrase': fake.word([fake.password(), None])
        }
        key = f"{entry['namespace']}.{entry['address']}.{entry['port']}"
        inventory[key] = entry
        credentials[key] = cred
        result[key] = cred.copy()
        result[key].update(entry)

    # Generate the inventory files
    random_dir = Path(f'{INVENTORY_PATH}_{random.random()}')
    random_dir.mkdir()
    # Write the inventory file
    inv_data = yaml.safe_dump(inventory)
    if not inv_data:
        assert False, "Unable to produce the device list"
    with open(f'{random_dir}/inv_0.yml', "w") as out_file:
        out_file.write(inv_data)

    # Encrypt and write the credential file
    cred_key = Fernet.generate_key()
    encryptor = Fernet(cred_key)

    cred_data = yaml.safe_dump(credentials)
    if not cred_data:
        assert False, "Unable to produce the credentials list"
    # Encrypt credential data
    enc_cred_data = encryptor.encrypt(cred_data.encode('utf-8'))
    with open(f'{random_dir}/cred_0', "w") as out_file:
        out_file.write(enc_cred_data.decode())

    yield result, random_dir, cred_key.decode()

    shutil.rmtree(random_dir)


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
async def test_get_device_list(monkeypatch, gen_random_inventory):
    """Test if the device list is correctly received and reconstructed
    """
    expected_dict, inventory_path, key = gen_random_inventory
    monkeypatch.setenv('SQ_CONTROLLER_POLLER_CRED', key)
    monkeypatch.setenv('SQ_INVENTORY_PATH', str(inventory_path))
    static_inv = StaticManagerInventory(MagicMock())
    # Check if the device list has been correctly obtained
    obtained_list = await static_inv._get_device_list()
    obtained_dict = {f"{o['namespace']}.{o['address']}.{o['port']}": o
                     for o in obtained_list}
    assert expected_dict == obtained_dict


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
