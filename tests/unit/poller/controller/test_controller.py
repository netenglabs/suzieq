import argparse
import asyncio
import os
from pathlib import Path
import signal
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
from suzieq.poller.controller.chunker.static import StaticChunker
from suzieq.poller.controller.controller import (DEFAULT_INVENTORY_PATH,
                                                 Controller)
from suzieq.poller.controller.manager.static import StaticManager
from suzieq.poller.controller.source.native import SqNativeFile
from suzieq.poller.controller.source.netbox import Netbox
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import load_sq_config, sq_get_config_file
from tests.conftest import create_dummy_config_file

# pylint: disable=protected-access
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

_CONFIG_FILE = ['tests/unit/poller/controller/data/suzieq-cfg.yaml']

_INVENTORY_FILE = ['tests/unit/poller/controller/data/inventory.yaml']

_DEFAULT_ARGS = {
    'inventory': None,
    'input_dir': None,
    'config': None,
    'debug': False,
    'exclude_services': None,
    'no_coalescer': False,
    'outputs': 'parquet',
    'output_dir': f'{os.path.abspath(os.curdir)}/sqpoller-output',
    'run_once': None,
    'service_only': None,
    'ssh_config_file': None,
    'update_period': None,
    'workers': None
}

_VALID_ARGS = [
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': True,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': 'tests/unit/poller/controller/data',
        'config': '',
        'debug': False,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': False,
        'exclude_services': 'macs',
        'no_coalescer': False,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': 'gather',
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': False,
        'exclude_services': 'macs',
        'no_coalescer': False,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    }
]

_INVALID_ARGS = [
    {
        'inventory': '',
        'input_dir': '/non-existent-folder',
        'config': '',
        'debug': True,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': None,
        'input_dir': None,
        'config': '',
        'debug': True,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': True,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': -1
    },
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': True,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': -1,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': True,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 4
    }
]


def generate_controller(args: Dict, inv_file: str = None,
                        conf_file: str = '') -> Controller:
    """Generate a Controller object

    Args:
        args (Dict): controller input args
        inv_file (str, optional): controller inventory file. Defaults to None.
        conf_file (str, optional): controller config file. Defaults to ''.

    Returns:
        Controller: the newly created Controller
    """
    if conf_file == '':
        conf_file = create_dummy_config_file()
    config = load_sq_config(config_file=conf_file)
    args = update_args(args, inv_file, conf_file)
    parse_args = generate_argparse(args)
    return Controller(parse_args, config)


def update_args(args: Dict, inv_file: str, conf_file: str) -> Dict:
    """ Add inventory file and config file in the correct spots inside the
    arguments

    Args:
        args (Dict): controller args
        inv_file (str): inventory file
        conf_file (str): config file

    Returns:
        Dict: updated args
    """
    args['inventory'] = inv_file
    args['config'] = conf_file
    return args


def generate_argparse(args: Dict) -> argparse.Namespace:
    """Generate an argpase.Namespace starting from a dictionary

    This is the only way to pass arguments to a Controller

    Args:
        args (Dict): controller args

    Returns:
        argparse.Namespace: args to be passed to the Controller
    """
    return argparse.Namespace(**args)


@pytest.fixture
def mock_static_manager():
    """Generate a mock for the static manager
    """

    def mock_init(self, data):
        self._workers_count = 1

    async def mock_1(self, data):
        pass

    async def mock_2(self):
        pass

    mng_mock = patch.multiple(StaticManager, __init__=mock_init,
                              _execute=mock_2, run=mock_2, apply=mock_1)
    # native_mock = patch.multiple(SqNativeFile)
    mng_mock.start()
    yield
    mng_mock.stop()


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('config_file', _CONFIG_FILE)
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
@pytest.mark.parametrize('args', _VALID_ARGS)
def test_controller_valid_args(config_file: str, inv_file: str, args: Dict):
    """Test controller with valid configuration

    Args:
        config_file (str): configuration file
        inv_file (str): inventory
        args (Dict): input arguments
    """
    c = generate_controller(args, inv_file, config_file)
    config = load_sq_config(config_file=config_file)

    poller_config = config['poller']

    assert c._input_dir == args['input_dir']

    if args['debug']:
        assert c.run_once == 'debug'
    elif args['input_dir']:
        assert c.run_once == 'input-dir'
    else:
        assert c.run_once == args['run_once']

    if not args['input_dir']:
        assert c._config['source']['path'] == args['inventory']

    assert c._config['manager']['type'] == poller_config['manager']['type']
    assert c._config['chunker']['type'] == poller_config['chunker']['type']
    assert c.inventory_timeout == poller_config['inventory-timeout']
    if not args['run_once']:
        assert c._no_coalescer == args['no_coalescer']
    else:
        assert c._no_coalescer is True
    assert c.period == args['update_period']

    manager_args = ['debug', 'exclude-services', 'outputs', 'config',
                    'output-dir', 'service-only', 'ssh-config-file', 'workers']
    for ma in manager_args:
        args_key = ma.replace('-', '_')
        assert c._config['manager'][ma] == args[args_key]


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('config_file', _CONFIG_FILE)
@pytest.mark.parametrize('args', _INVALID_ARGS)
def test_controller_invalid_args(config_file: str, args: Dict):
    """Test controller with invalid configuration

    Args:
        config_file (str): config file
        args (Dict): controller arguments
    """
    config = load_sq_config(config_file=config_file)

    if args['inventory'] is None:
        config['poller']['inventory-file'] = '/non-existent-inventory.yml'
    elif args['workers'] == 4:
        config['poller']['inventory-timeout'] = -1

    parse_args = generate_argparse(args)

    with pytest.raises(SqPollerConfError):
        Controller(parse_args, config)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
def test_default_controller_config():
    """Test controller default configuration
    """

    # No inventory file in default directory
    with pytest.raises(SqPollerConfError):
        generate_controller(args=_DEFAULT_ARGS.copy(), conf_file=None)

    # Create inventory in the default directory
    def_file = Path(DEFAULT_INVENTORY_PATH)
    def_file.touch(exist_ok=False)

    c = generate_controller(args=_DEFAULT_ARGS.copy(), conf_file=None)
    assert c._config['source']['path'] == DEFAULT_INVENTORY_PATH
    assert c._input_dir is None
    assert c._no_coalescer is False
    assert c._config['manager']['config'] == sq_get_config_file(None)
    assert c._config['manager']['workers'] == 1
    assert c.period == 3600
    assert c.run_once is None
    manager_args = ['debug', 'exclude-services', 'outputs',
                    'output-dir', 'service-only', 'ssh-config-file']
    for ma in manager_args:
        args_key = ma.replace('-', '_')
        assert c._config['manager'][ma] == _DEFAULT_ARGS[args_key]

    # Remove the default inventory file
    os.remove(def_file)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
def test_controller_init_plugins(inv_file: str):
    """Test Controller.init_plugins function

    Args:
        inv_file (str): inventory
    """
    c = generate_controller(args=_DEFAULT_ARGS.copy(), inv_file=inv_file)

    # wrong plugin type
    with pytest.raises(SqPollerConfError):
        c.init_plugins('unknown-plugin-type')

    # check all plugins are loaded correctly
    src_plugins = c.init_plugins('source')
    assert len(set(src_plugins)) == len(src_plugins) == 2
    for v in src_plugins:
        if not isinstance(v, (Netbox, SqNativeFile)):
            assert False


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
def test_controller_init(inv_file: str, mock_static_manager):
    """Test Controler.init function

    Args:
        inv_file (str): inventory file
    """

    # Test common initialization
    c = generate_controller(args=_DEFAULT_ARGS.copy(), inv_file=inv_file)

    c.init()
    assert len(set(c.sources)) == len(c.sources) == 2
    for v in c.sources:
        if not isinstance(v, (Netbox, SqNativeFile)):
            assert False

    assert isinstance(c.chunker, StaticChunker)
    assert isinstance(c.manager, StaticManager)

    # Test input dir
    c = generate_controller(args=_DEFAULT_ARGS.copy(), inv_file=inv_file)
    c._input_dir = 'my/directory'

    c.init()
    assert c.sources == []
    assert c.chunker is None
    assert isinstance(c.manager, StaticManager)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
@pytest.mark.asyncio
async def test_controller_run(inv_file: str, mock_static_manager):
    """Test Controller.run function

    Args:
        inv_file (str): inventory file
    """

    netbox_inventory = {
        'my-ns.192.168.0.1.90': {
            'address': '192.168.0.1',
            'namespace': 'my-ns',
            'port': 90,
            'transport': 'ssh',
            'devtype': 'panos',
            'hostname': 'host0',
            'jump_host': None,
            'jump_host_key_file': None,
            'ignore_known_hosts': False,
            'username': 'user',
            'password': 'pass',
            'ssh_keyfile': 'keyfile',
            'passphrase': 'pass'
        },
        'my-ns.1.1.1.1.22': {
            'address': '1.1.1.1',
            'namespace': 'my-ns',
            'port': 22,
            'transport': 'ssh',
            'devtype': 'panos',
            'hostname': 'host1',
            'jump_host': None,
            'jump_host_key_file': None,
            'ignore_known_hosts': False,
            'username': 'user',
            'password': 'pass',
            'ssh_keyfile': 'keyfile',
            'passphrase': 'pass'
        }
    }

    # this device is also present in netbox inventory
    native_inventory = {
        'my-ns.1.1.1.1.22': {
            'address': '1.1.1.1',
            'namespace': 'my-ns',
            'port': 22,
            'transport': 'ssh',
            'devtype': 'panos',
            'hostname': 'host1',
            'jump_host': None,
            'jump_host_key_file': None,
            'ignore_known_hosts': False,
            'username': 'user',
            'password': 'pass',
            'ssh_keyfile': 'keyfile',
            'passphrase': 'pass'
        }
    }

    async def mock_netbox_run(self):
        self.set_inventory(netbox_inventory)
        # emulate a CTRL+C by the user to test if the '_stop' function
        await asyncio.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    # pylint: disable=unused-argument
    def mock_native_load(self, inv):
        self.set_inventory(native_inventory)

    # Generate fixed outputs to test if the function has been called
    async def mock_manager_apply(self, inv_chunks):
        self.mock_inv_chunks = inv_chunks

    async def mock_manager_run(self):
        self.mng_mock_run = True

    async def mock_launch_with_dir(self):
        self.mock_launched = True

    # test usual run function behaviour
    args = _DEFAULT_ARGS.copy()
    c = generate_controller(args=args, inv_file=inv_file)
    with patch.object(c, '_stop', MagicMock(side_effect=c._stop)) as stop_mock:
        with patch.multiple(SqNativeFile, _load=mock_native_load):
            with patch.multiple(Netbox, run=mock_netbox_run):
                with patch.multiple(StaticManager, apply=mock_manager_apply,
                                    run=mock_manager_run):
                    c.init()
                    assert await c.sources[0].get_inventory() == \
                        native_inventory
                    await c.run()
                    # test 'run' functions are called
                    assert await c.sources[1].get_inventory() == \
                        netbox_inventory
                    assert c.manager.mng_mock_run

                    # check duplicated are removed
                    assert c.manager.mock_inv_chunks == [netbox_inventory]

                    stop_mock.assert_called()

    # test with input-dir argument
    args = _DEFAULT_ARGS.copy()
    args['run_once'] = True
    args['input_dir'] = 'tests/unit/poller/controller/data/'

    c = generate_controller(args=args, inv_file=inv_file)
    c.init()
    with patch.multiple(StaticManager, launch_with_dir=mock_launch_with_dir,
                        run=mock_manager_run):
        await c.run()
        assert c.manager.mock_launched
        assert c.manager.mng_mock_run


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
def test_controller_init_errors(inv_file: str, mock_static_manager):
    """Test Controller.init function errors

    Args:
        inv_file (str): inventory file
    """

    def mock_init_plugins(self, plugin_type: str):
        """This mock method is used to test all the possible errors
        generated from the function 'init_plugins'

        It writes into self.mock_tested_plugins the plugins which have
        been already tested with a wrong value.

        Every time the wrong value is returned, the 'plugin_type' is
        appended to self.mock_tested_plugins. In this way, the next
        iteration will test the next plugin
        """
        if not hasattr(self, 'mock_tested_plugins'):
            self.mock_tested_plugins = []
        if plugin_type in ['chunker', 'manager']:
            if plugin_type in self.mock_tested_plugins:
                return [None]
            else:
                self.mock_tested_plugins.append(plugin_type)
                return [None, None]
        elif plugin_type == 'source':
            if plugin_type in self.mock_tested_plugins:
                return {'key': 'value'}
            else:
                self.mock_tested_plugins.append(plugin_type)
                return {}

    c = generate_controller(args=_DEFAULT_ARGS.copy(), inv_file=inv_file)

    # empty 'source' plugins
    with patch.multiple(Controller, init_plugins=mock_init_plugins):

        # test 'source' error
        with pytest.raises(SqPollerConfError,
                           match="The inventory file doesn't have any source"):
            c.init()

        # test 'chunker' error
        with pytest.raises(SqPollerConfError,
                           match='Only 1 Chunker at a time is supported'):
            c.init()

        # test 'manager' error
        with pytest.raises(SqPollerConfError,
                           match='Only 1 manager at a time is supported'):
            c.init()


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
@pytest.mark.asyncio
async def test_controller_empty_inventory(inv_file: str, mock_static_manager):
    """Test that the controller launches an exception with an
    empty global inventory

    Args:
        inv_file (str): inventory file
    """
    # pylint: disable=unused-argument

    def mock_empty_load(self, inv):
        self.set_inventory({})

    async def mock_empty_inventory(self):
        self.set_inventory({})

    args = _DEFAULT_ARGS.copy()
    c = generate_controller(args=args, inv_file=inv_file)

    with patch.multiple(SqNativeFile, _load=mock_empty_load):
        with patch.multiple(Netbox, run=mock_empty_inventory):
            c.init()
            with pytest.raises(InventorySourceError,
                               match='No devices to poll'):
                await c.run()


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
@pytest.mark.parametrize('config_file', _CONFIG_FILE)
@pytest.mark.asyncio
async def test_controller_run_timeout_error(inv_file: str, config_file: str,
                                            mock_static_manager):
    """Test that the controller launches an exception if the get_inventory
    function doesn't return before the timeout

    Args:
        inv_file (str): inventory file
        config_file (str): config file. Here the timeout is set to 1 second
    """
    # pylint: disable=unused-argument
    async def mock_netbox_run(self):
        """This function doesn't call Source.set_inventory resulting
        into an event not set and a Timeout error on the
        Source.get_inventory function
        """

    args = _DEFAULT_ARGS.copy()
    c = generate_controller(args, inv_file, config_file)
    c.init()
    with patch.multiple(Netbox, run=mock_netbox_run):
        with pytest.raises(InventorySourceError):
            await c.run()
