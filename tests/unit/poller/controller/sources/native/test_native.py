import asyncio
from typing import List

import pytest
import yaml
from suzieq.poller.controller.source.native import SqNativeFile
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.controller.sources.utils import (get_sample_config,
                                                        read_result_data)

_SAMPLE_CONFIG = get_sample_config('native')

_RESULT_PATH = ['tests/unit/poller/controller/sources/data/native/results/'
                'results.yaml']

_VALID_HOSTS = ['tests/unit/poller/controller/sources/data/native/inventory/'
                'valid_hosts.yaml']


def load_hosts(path: str) -> List:
    """Load hosts from path

    Args:
        path (str): hosts file path

    Returns:
        List: list of hosts
    """
    with open(path, 'r') as f:
        return yaml.safe_load(f)


@pytest.mark.native
@pytest.mark.source
@pytest.mark.parametrize('hosts_file', _VALID_HOSTS)
@pytest.mark.parametrize('result_path', _RESULT_PATH)
@pytest.mark.asyncio
async def test_valid_config(hosts_file: str, result_path: str):
    """Test if the inventory is loaded correctly

    Args:
        hosts_file (str): file containing hosts in the inventory file
        result_path (str): file containing result
    """
    config = _SAMPLE_CONFIG
    config['hosts'] = load_hosts(hosts_file)

    src = SqNativeFile(config)

    assert src._name == config['name']
    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == read_result_data(result_path)


@pytest.mark.source
@pytest.mark.native
@pytest.mark.asyncio
async def test_invalid_hosts():
    """Test invalid hosts param
    """

    config = _SAMPLE_CONFIG

    # empty hosts
    config['hosts'] = []

    with pytest.raises(InventorySourceError):
        SqNativeFile(config)

    # invalid hosts. All hosts will be ignored
    config['hosts'] = [
        # no 'url' key
        {'not-url': 'ssh://vagrant@192.168.0.1 password=my-password'},
        # 'password:' instead of 'password='
        {'url': 'ssh://vagrant@192.168.0.1 password:my-password'},
        # not a dictionary
        "url= ssh://vagrant@192.168.0.1 password=my-password",
        # key doesn't exists
        {'url': 'ssh://vagrant@192.168.0.1 keyfile=wrong/key/path'}
    ]

    src = SqNativeFile(config)
    inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert inv == {}
