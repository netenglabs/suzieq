import asyncio
from typing import List

import pytest
import yaml
from suzieq.poller.controller.source.native import SqNativeFile
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.controller.utils import (get_src_sample_config,
                                                read_data)

_SAMPLE_CONFIG = get_src_sample_config('native')

_DATA_PATH = [
    {
        'hosts': 'tests/unit/poller/controller/sources/data/native/inventory/'
     'valid_hosts.yaml',
     'results': 'tests/unit/poller/controller/sources/data/native/results/'
                'results.yaml'}
]


@pytest.mark.native
@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.parametrize('data_path', _DATA_PATH)
@pytest.mark.asyncio
async def test_valid_config(data_path: str):
    """Test if the inventory is loaded correctly

    Args:
        data_path (str): file containing result and hosts
    """
    config = _SAMPLE_CONFIG
    config['hosts'] = read_data(data_path['hosts'])

    src = SqNativeFile(config)

    assert src.name == config['name']
    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == read_data(data_path['results'])


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
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

    # hosts field not set
    config.pop('hosts')
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
