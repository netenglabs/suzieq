import asyncio
import json
import time
from multiprocessing import Process
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from suzieq.poller.controller.credential_loader.static import StaticLoader
from suzieq.poller.controller.source.netbox import Netbox
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.controller.sources.netbox.netbox_faker import \
    NetboxFaker
from tests.unit.poller.controller.sources.netbox.netbox_rest_server import \
    NetboxRestApp
from tests.unit.poller.shared.utils import (get_free_port,
                                            get_src_sample_config)

# pylint: disable=redefined-outer-name

_SERVER_CONFIGS = [
    {
        'namespace': 'netbox-ns',
        'use_ssl': '',
        'tag': 'suzieq',
        'count': 20
    },
    {
        'namespace': 'netbox-sitename',
        'use_ssl': 'self-signed',
        'tag': 'suzieq',
        'count': 90
    }
]


def fake_netbox_data(server_conf: Dict) -> Tuple[Dict, Dict]:
    """Generate fake data for netbox

    Args:
        server_conf (Dict): server configuration

    Returns:
        Tuple[Dict, Dict]: fake server data, fake expected inventory
    """
    config = {
        'count': server_conf['count'],
        'tag-value': server_conf['tag'],
        'tag-prob': 0.9,
        'ip4-prob': 0.5,
        'ip6-prob': 0.9,
        'site-count': 5,
        'namespace': server_conf['namespace']
    }
    n = NetboxFaker(config)
    return n.generate_data()


def read_json_file(path: str) -> Any:
    """Read result from file

    Args:
        path (str): path of result file

    Returns:
        [Any]: content of the file
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise RuntimeError(f'Invalid file to read {path}')
    with open(file_path, 'r') as f:
        return json.load(f)


def update_config(server_conf: Dict, config: Dict) -> Dict:
    """Set the netbox configuration correctly to connect to the
    server

    Args:
        server_conf (Dict): server configuration
        config (Dict): netbox configuration

    Returns:
        Dict: updated netbox configuration
    """
    config['tag'] = server_conf['tag']
    config['namespace'] = server_conf['namespace']
    config['url'] = 'http'
    if server_conf['use_ssl']:
        config['url'] = 'https'
        if server_conf['use_ssl'] == 'self-signed':
            config['ssl-verify'] = False
    config['url'] += f'://127.0.0.1:{server_conf["port"]}'
    return config

# ATTENTION: This fixture is executed for each test. Every test will spawn
#            a process. This is not the best solution but it works. The
#            code will select a random free port and avoid ports conficts.


@pytest.fixture(scope="session", autouse=True)
def rest_server_manager():
    """Starts the server at the beginning of tests
    """
    server_conf_list = _SERVER_CONFIGS
    proc_list = []
    for server_conf in server_conf_list:
        serv_data, exp_inv = fake_netbox_data(server_conf)
        server_conf['result'] = exp_inv
        server_conf['port'] = get_free_port()
        nra = NetboxRestApp(data=serv_data, port=server_conf['port'],
                            use_ssl=server_conf['use_ssl'])
        p = Process(target=nra.start)
        p.start()
        proc_list.append(p)
    # wait for REST servers to start
    time.sleep(0.5)
    yield
    _ = [p.terminate() for p in proc_list]


@pytest.fixture
def default_config() -> Dict:
    """Generate a default netbox config

    Returns:
        Dict: netbox config

    Yields:
        Iterator[Dict]: [description]
    """
    yield get_src_sample_config('netbox')


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.netbox
@pytest.mark.asyncio
@pytest.mark.parametrize('server_conf', _SERVER_CONFIGS)
async def test_valid_config(server_conf: Dict, default_config):
    """Tests if the pulled inventory is valid

    Args:
        server_conf(Dict): server configuration
    """
    # pylint: disable=protected-access
    config = default_config
    config = update_config(server_conf, config)

    src = Netbox(config)
    assert src.name == config['name']
    assert src._protocol == config['url'].split(':')[0]
    assert src._host == '127.0.0.1'
    assert src._port == server_conf['port']
    assert src._tag == config['tag']
    assert src._token == config['token']
    assert isinstance(src._auth, StaticLoader)
    if config.get('ssl-verify') is not None:
        assert src._ssl_verify == config['ssl-verify']
    else:
        # default ssl config
        if src._protocol == 'http':
            assert src._ssl_verify is False
        elif src._protocol == 'https':
            assert src._ssl_verify is True

    await asyncio.wait_for(src.run(), 10)

    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == server_conf['result']


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.netbox
@pytest.mark.parametrize('server_conf', _SERVER_CONFIGS)
@pytest.mark.asyncio
async def test_netbox_invalid_server_config(server_conf: Dict, default_config):
    """Test netbox recognize invalid server configuration

    Args:
        server_conf (Dict): server configuration
    """
    config = default_config
    config = update_config(server_conf, config)

    # set unexistent url
    old_url, config['url'] = config['url'], 'http://0.0.0.0:80'
    with pytest.raises(InventorySourceError):
        src = Netbox(config)
        await asyncio.wait_for(src.run(), 10)
    config['url'] = old_url

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


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.netbox
def test_netbox_invalid_config(default_config):
    """Test invalid netbox configurations
    """
    config = default_config

    # set invalid url
    old_url, config['url'] = config['url'], 'not_an_url'
    with pytest.raises(InventorySourceError, match=r".* invalid url provided"):
        Netbox(config)
    config['url'] = old_url

    # add invalid field
    config['invalid'] = 'field'
    with pytest.raises(InventorySourceError, match=r".* unknown fields "
                       r"\['invalid'\]"):
        Netbox(config)
    config.pop('invalid')

    # missing auth
    old_auth = config.pop('auth')
    with pytest.raises(InventorySourceError, match=r".* Netbox must have an "
                       "'auth' set in the 'namespaces' section"):
        Netbox(config)
    config['auth'] = old_auth

    # missing mandatory field
    old_token = config.pop('token')
    with pytest.raises(InventorySourceError, match=r".* Invalid config "
                       r"missing fields \['token'\]"):
        Netbox(config)
    config['token'] = old_token


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.netbox
@pytest.mark.parametrize('server_conf', _SERVER_CONFIGS)
@pytest.mark.asyncio
async def test_ssl_missconfiguration(server_conf: Dict, default_config):
    """Test possible ssl missconfigurations

    Args:
        server_conf (Dict): server configuration
    """
    config = default_config
    config = update_config(server_conf, config)

    if server_conf['use_ssl'] == 'self-signed':
        # verify ssl over self-signed certificate
        config['ssl-verify'] = True

        with pytest.raises(InventorySourceError):
            src = Netbox(config)
            await asyncio.wait_for(src.run(), 10)
    elif server_conf['use_ssl'] == '':
        # set ssl verify over an http connection
        config['ssl-verify'] = True

        with pytest.raises(InventorySourceError):
            src = Netbox(config)
            await asyncio.wait_for(src.run(), 10)


@pytest.mark.controller_source
@pytest.mark.controller
@pytest.mark.poller
@pytest.mark.netbox
def test_netbox_automatic_ssl_verify(default_config):
    """Test netbox ssl verify is set correctly if not specified
    """
    # pylint: disable=protected-access
    config = default_config
    if 'ssl-verify' in config:
        config.pop('ssl-verify')
    config['url'] = 'http://127.0.0.1:22'

    n = Netbox(config)
    assert not n._ssl_verify

    config['url'] = 'https://127.0.0.1:22'
    n = Netbox(config)
    assert n._ssl_verify
