import asyncio
import time
from multiprocessing import Process
from typing import Dict

import pytest
from suzieq.shared.exceptions import InventorySourceError
from suzieq.poller.controller.source.netbox import Netbox
from tests.unit.poller.controller.sources.netbox.netbox_rest_server import \
    NetboxRestApp
from tests.unit.poller.controller.utils import (get_src_sample_config,
                                                read_data)

_SAMPLE_CONFIG = get_src_sample_config('netbox')

_SERVER_CONFIGS = [
    {
        'port': 9000,
        'name': 'netbox0',
        'result': 'tests/unit/poller/controller/sources/data/netbox/results/'
        'results0.yaml'
    }
]


# ATTENTION: This fixture is executed for each test. Every test will spawn
#            a process. This is not the best solution but it works for now
#            Adding an element in _SERVER_CONFIGS will cause some problems
@pytest.fixture(scope="session", autouse=True, params=[_SERVER_CONFIGS])
def manager_rest_server(request):
    """Starts the server at the beginning of tests
    """
    server_conf_list = request.param
    proc_list = []
    for server_conf in server_conf_list:
        nra = NetboxRestApp(name=server_conf['name'], port=server_conf['port'])
        p = Process(target=nra.start)
        p.start()
        proc_list.append(p)
    # wait for REST servers to start
    time.sleep(1)
    yield
    _ = [p.terminate() for p in proc_list]


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.netbox
@pytest.mark.asyncio
@pytest.mark.parametrize('server_conf', _SERVER_CONFIGS)
async def test_valid_config(server_conf: Dict):
    """Tests if the pulled inventory is valid

    Args:
        server_conf(Dict): server configuration
    """
    config = _SAMPLE_CONFIG
    config['url'] = f'http://127.0.0.1:{server_conf["port"]}'

    src = Netbox(config)
    assert src._name == config['name']

    await asyncio.wait_for(src.run(), 10)

    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == read_data(server_conf['result'])


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.netbox
@pytest.mark.parametrize('server_conf', _SERVER_CONFIGS)
@pytest.mark.asyncio
async def test_invalid_config(server_conf: Dict):
    """Test invalid configuration

    Args:
        server_conf (Dict): server configuration
    """
    config = _SAMPLE_CONFIG

    # set an invalid url
    config['url'] = f'http://127.0.0.1:{server_conf["port"]+1000}'
    with pytest.raises(InventorySourceError):
        src = Netbox(config)
        await asyncio.wait_for(src.run(), 10)
    config['url'] = f'http://127.0.0.1:{server_conf["port"]}'

    # set invalid tag
    old_tag, config['tag'] = config['tag'], 'wrong_tag'
    src = Netbox(config)
    await asyncio.wait_for(src.run(), 10)
    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == {}
    config['tag'] = old_tag

    # set invalid token
    old_token, config['token'] = config['token'], 'WRONG-TOKEN'
    with pytest.raises(InventorySourceError):
        src = Netbox(config)
        await asyncio.wait_for(src.run(), 10)
    config['token'] = old_token
