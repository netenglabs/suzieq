import asyncio
import json
import time
from multiprocessing import Process
from pathlib import Path
from typing import Any, Dict, Tuple
from pydantic import ValidationError

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
        'tag': ['suzieq'],
        'count': 20
    },
    {
        'namespace': 'netbox-sitename',
        'use_ssl': 'self-signed',
        'tag': ['suzieq', 'suzieq-2'],
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
        'namespace': server_conf['namespace'],
        'seed': 1111
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
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_netbox
@pytest.mark.asyncio
@pytest.mark.parametrize('server_conf', _SERVER_CONFIGS)
async def test_valid_config(server_conf: Dict, default_config):
    """Tests if the pulled inventory is valid

    Args:
        server_conf(Dict): server configuration
    """
    config = default_config
    config = update_config(server_conf, config)

    exp_tags = []
    for tags in config['tag']:
        exp_tags.append([t.strip() for t in tags.split(',')])

    src = Netbox(config.copy())
    assert src.name == config['name'], 'wrong name'
    assert src._server.protocol == config['url'].split(':')[0], \
        'wrong server protocol'
    assert src._server.host == '127.0.0.1', 'wrong server host'
    assert src._server.port == str(server_conf['port']), 'wrong server port'
    assert src._data.tag == exp_tags, 'wrong tag'
    assert src._data.token == config['token'], 'wrong token'
    assert isinstance(src._auth, StaticLoader), 'wrong auth object'
    if config.get('ssl-verify') is not None:
        assert src._data.ssl_verify == config['ssl-verify'], 'wrong ssl_verify'
    else:
        # default ssl config
        if src._server.protocol == 'http':
            assert src._data.ssl_verify is False, \
                'with http protocol, ssl_verify must be False'
        elif src._server.protocol == 'https':
            assert src._data.ssl_verify is True, \
                'with https protocol, ssl_verify must be True'

    await asyncio.wait_for(src.run(), 10)

    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == server_conf['result']


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_netbox
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
        src = Netbox(config.copy())
        await asyncio.wait_for(src.run(), 10)
    config['url'] = old_url

    # set invalid tag
    old_tag, config['tag'] = config['tag'], ['wrong_tag']
    src = Netbox(config.copy())
    await asyncio.wait_for(src.run(), 10)
    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == {}
    config['tag'] = old_tag

    # set invalid token
    old_token, config['token'] = config['token'], 'WRONG-TOKEN'
    with pytest.raises(InventorySourceError):
        src = Netbox(config.copy())
        await asyncio.wait_for(src.run(), 10)
    config['token'] = old_token


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_netbox
def test_netbox_invalid_config(default_config):
    """Test invalid netbox configurations
    """
    config = default_config

    # set invalid url
    old_url, config['url'] = config['url'], 'not_an_url'
    with pytest.raises(ValidationError,
                       match=r".* Unable to parse hostname .*"):
        Netbox(config.copy())
    config['url'] = old_url

    # add invalid field
    config['invalid'] = 'field'
    with pytest.raises(ValidationError, match=r".* extra fields not "
                       r"permitted .*"):
        Netbox(config.copy())
    config.pop('invalid')

    # missing auth
    old_auth = config.pop('auth')
    with pytest.raises(InventorySourceError, match=r".* Netbox must have an "
                       "'auth' set in the 'namespaces' section"):
        Netbox(config.copy())
    config['auth'] = old_auth

    # missing mandatory field
    old_token = config.pop('token')
    with pytest.raises(ValidationError, match=r".* field required .*"):
        Netbox(config.copy())
    config['token'] = old_token


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_netbox
@pytest.mark.parametrize('server_conf', _SERVER_CONFIGS)
@pytest.mark.asyncio
async def test_ssl_misconfiguration(server_conf: Dict, default_config):
    """Test possible ssl misconfigurations

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

        with pytest.raises(ValidationError):
            src = Netbox(config)
            await asyncio.wait_for(src.run(), 10)


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_netbox
def test_netbox_automatic_ssl_verify(default_config):
    """Test netbox ssl verify is set correctly if not specified
    """
    config = default_config
    if 'ssl-verify' in config:
        config.pop('ssl-verify')
    config['url'] = 'http://127.0.0.1:22'

    n = Netbox(config.copy())
    assert not n._data.ssl_verify, 'Expected ssl_verify=False'

    config['url'] = 'https://127.0.0.1:22'
    n = Netbox(config.copy())
    assert n._data.ssl_verify, 'Expected ssl_verify=True'


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_netbox
def test_netbox_tags(default_config):
    """Test netbox tags are correctly parsed
    """
    config = default_config

    # test string tags are converted to list
    config['tag'] = 'my-tag'

    n = Netbox(config.copy())
    assert n._data.tag == [['my-tag']], 'Single tag not converted in list'

    # test and/or tag logic
    config['tag'] = [
        'alpha, bravo',
        'charlie',
        'delta, echo, foxtrot'
    ]

    n = Netbox(config.copy())
    url_address = f'{n._server.protocol}://{n._server.host}:'\
        f'{n._server.port}/api/dcim/devices/?'
    exp_url_list = [
        url_address + 'tag=alpha&tag=bravo',
        url_address + 'tag=charlie',
        url_address + 'tag=delta&tag=echo&tag=foxtrot'
    ]
    url_list = n._get_url_list()
    assert sorted(url_list) == sorted(exp_url_list), \
        f'Wrong url list {url_list}'
