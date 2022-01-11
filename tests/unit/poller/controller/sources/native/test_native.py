import asyncio
from typing import Dict

import pytest
from suzieq.poller.controller.source.native import SqNativeFile
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.shared.utils import (get_src_sample_config,
                                            read_yaml_file)

# pylint: disable=redefined-outer-name

_DATA_PATH = [
    {
        'hosts': 'tests/unit/poller/controller/sources/native/data/inventory/'
        'valid_hosts.yaml',

        'results': 'tests/unit/poller/controller/sources/native/data/results/'
        'results.yaml'}
]


@pytest.fixture
def default_config() -> Dict:
    """return a default native configuration

    Yields:
        Dict: native config
    """
    yield get_src_sample_config('native')


@pytest.mark.native
@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.parametrize('data_path', _DATA_PATH)
@pytest.mark.asyncio
async def test_valid_config(data_path: str, default_config):
    """Test if the inventory is loaded correctly

    Args:
        data_path (str): file containing result and hosts
    """
    config = default_config
    config['hosts'] = read_yaml_file(data_path['hosts'])

    src = SqNativeFile(config)

    assert src.name == config['name']
    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == read_yaml_file(data_path['results'])


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.native
@pytest.mark.asyncio
async def test_invalid_hosts(default_config):
    """Test invalid hosts param
    """

    config = default_config

    # empty hosts
    config['hosts'] = []

    with pytest.raises(InventorySourceError):
        SqNativeFile(config)

    # 'hosts' not a list
    config['hosts'] = {'not': 'valid'}
    with pytest.raises(InventorySourceError):
        SqNativeFile(config)

    # hosts field not set
    config.pop('hosts')
    with pytest.raises(InventorySourceError):
        SqNativeFile(config)

    # invalid hosts. Only the last host will be loaded
    exp_inventory = {
        'native-ns.192.168.0.1.22': {
            'address': '192.168.0.1',
            'devtype': None,
            'hostname': None,
            'ignore_known_hosts': False,
            'jump_host': None,
            'jump_host_key_file': None,
            'namespace': 'native-ns',
            'password': 'my-password',
            'port': 22,
            'ssh_keyfile': None,
            'transport': 'ssh',
            'username': 'vagrant'
        }
    }
    host = exp_inventory['native-ns.192.168.0.1.22']
    valid_url = {
        'url': f"{host['transport']}://{host['address']}:{host['port']} "
        f"password={host['password']} username={host['username']} wrong=field"
    }
    config['hosts'] = [
        # no 'url' key
        {'not-url': 'ssh://vagrant@192.168.0.1 password=my-password'},
        # 'password:' instead of 'password='
        {'url': 'ssh://vagrant@192.168.0.1 password:my-password'},
        # not a dictionary
        "url= ssh://vagrant@192.168.0.1 password=my-password",
        # key doesn't exists
        {'url': 'ssh://vagrant@192.168.0.1 keyfile=wrong/key/path'},
        # ignore a parameter
        valid_url
    ]

    src = SqNativeFile(config)
    inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert inv == exp_inventory


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.native
@pytest.mark.asyncio
def test_validate_inventory(default_config):
    """Check that validate_inventory raise correctly
    """
    config = default_config

    # wrong transport
    config['hosts'] = [
        {'url': 'wrong://vagrant@192.168.0.1 password=my-password'}
    ]
    with pytest.raises(InventorySourceError):
        SqNativeFile(config)

    # wrong ip address
    config['hosts'] = [
        {'url': 'ssh://vagrant@192_168_0_1 password=my-password'}
    ]
    with pytest.raises(InventorySourceError):
        SqNativeFile(config)
