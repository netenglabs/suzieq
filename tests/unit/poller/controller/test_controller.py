import argparse
import asyncio
import os
import signal
from tempfile import NamedTemporaryFile
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
import suzieq.poller.controller.controller as controller_module
from suzieq.poller.controller.chunker.static import StaticChunker
from suzieq.poller.controller.controller import Controller
from suzieq.poller.controller.manager.static import StaticManager
from suzieq.poller.controller.source.native import SqNativeFile
from suzieq.poller.controller.source.netbox import Netbox
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file, get_async_task_mock

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
        'service_only': 'bgp routes',
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
        'service_only': 'mlag routes',
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
        'service_only': 'interfaces routes',
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
        'service_only': 'device routes',
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
        'service_only': 'bgp routes',
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
        'service_only': 'mlag routes',
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
        'service_only': 'interfaces routes',
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
        'service_only': 'device routes',
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
        'service_only': 'bgp routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 4
    }
]


def generate_controller(args: Dict, inv_file: str = None,
                        conf_file: str = None) -> Controller:
    """Generate a Controller object

    Args:
        args (Dict): controller input args
        inv_file (str, optional): controller inventory file. Defaults to None.
        conf_file (str, optional): controller config file. Defaults to ''.

    Returns:
        Controller: the newly created Controller
    """
    if not conf_file:
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
def mock_plugins():
    """Generate a mock for controller plugins
    """

    async def mock_mng_run(self):
        pass

    def mock_src_init(self, inv, validate=False):
        """This function mocks sources __init__

        It contains the call to set_device. By default it
        does nothing, but it can be overrided to add some
        functionalities in the init function
        For example it is used to push a new inventory
        """
        self._name = 'name'
        self._inv_is_set = False
        self._inv_is_set_event = asyncio.Event()
        self.mocked_inv = inv
        self.set_device()
        self._load(inv)

    def mock_get_name(self):
        return self._name

    def mock_set_inventory(self, inv):
        self._inventory = inv.copy()
        if not self._inv_is_set:
            self._inv_is_set = True
            self._inv_is_set_event.set()

    async def mock_get_inventory(self):
        if not self._inv_is_set:
            await asyncio.wait_for(self._inv_is_set_event.wait(), 2)
        return self._inventory

    def mock_native_load(self, inv):
        self.set_inventory(self.mocked_inv)

    async def mock_netbox_run(self):
        self.set_inventory(self.mocked_inv)

    def mock_chunk(self, inv, n):
        return [inv]

    mng_mock = patch.multiple(StaticManager, _execute=MagicMock(),
                              run=mock_mng_run, apply=get_async_task_mock(),
                              get_n_workers=MagicMock(return_value=1),
                              __init__=MagicMock(return_value=None))

    native_mock = patch.multiple(SqNativeFile, __init__=mock_src_init,
                                 set_inventory=mock_set_inventory,
                                 get_inventory=mock_get_inventory,
                                 name=mock_get_name,
                                 _load=mock_native_load,
                                 set_device=MagicMock())

    netbox_mock = patch.multiple(Netbox, __init__=mock_src_init,
                                 set_inventory=mock_set_inventory,
                                 get_inventory=mock_get_inventory,
                                 name=mock_get_name,
                                 _load=MagicMock(), run=mock_netbox_run,
                                 set_device=MagicMock())

    chunker_mock = patch.multiple(StaticChunker, chunk=mock_chunk,
                                  __init__=MagicMock(return_value=None))

    mocked_plugins = [mng_mock, native_mock, netbox_mock, chunker_mock]
    for m in mocked_plugins:
        m.start()
    yield
    for m in mocked_plugins:
        m.stop()


@pytest.fixture
def default_args() -> Dict:
    """Return default args

    Yields:
        Dict: default args
    """
    yield _DEFAULT_ARGS.copy()


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
        assert c.single_run_mode == 'debug'
    elif args['input_dir']:
        assert c.single_run_mode == 'input-dir'
    else:
        assert c.single_run_mode == args['run_once']

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
def test_missing_default_inventory(default_args):
    """Test if the controller launches and exception if no inventory if
    passed in the configuration and there is no file in the default path
    """
    args = default_args
    with patch.multiple(controller_module,
                        DEFAULT_INVENTORY_PATH='/not/a/path'):
        with pytest.raises(SqPollerConfError):
            generate_controller(args=args)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
def test_default_controller_config(default_args):
    """Test controller default configuration
    """
    args = default_args

    with NamedTemporaryFile(suffix='yml') as tmpfile:
        with patch.multiple(controller_module,
                            DEFAULT_INVENTORY_PATH=tmpfile.name):
            c = generate_controller(args=args)
            assert c._config['source']['path'] == tmpfile.name
            assert c._input_dir is None
            assert c._no_coalescer is False
            assert c._config['manager']['workers'] == 1
            assert c.period == 3600
            assert c._single_run_mode is None
            manager_args = ['debug', 'exclude-services', 'outputs',
                            'output-dir', 'service-only', 'ssh-config-file']
            for ma in manager_args:
                args_key = ma.replace('-', '_')
                assert c._config['manager'][ma] == args[args_key]


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
def test_controller_init_plugins(inv_file: str, default_args):
    """Test Controller.init_plugins function

    Args:
        inv_file (str): inventory
    """
    c = generate_controller(args=default_args, inv_file=inv_file)

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
def test_controller_init(inv_file: str, mock_plugins, default_args):
    """Test Controler.init function

    Args:
        inv_file (str): inventory file
    """
    args = default_args
    # Test common initialization
    c = generate_controller(args=args, inv_file=inv_file)

    c.init()
    assert len(set(c.sources)) == len(c.sources) == 2
    for v in c.sources:
        if not isinstance(v, (Netbox, SqNativeFile)):
            assert False

    assert isinstance(c.chunker, StaticChunker)
    assert isinstance(c.manager, StaticManager)

    # Test input dir
    c = generate_controller(args=args, inv_file=inv_file)
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
async def test_controller_run(inv_file: str, mock_plugins,
                              default_args):
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

    def mock_native_set_device(self):
        self.mocked_inv = native_inventory

    async def mock_netbox_run(self):
        self.set_inventory(netbox_inventory.copy())
        # emulate a CTRL+C by the user to test if the '_stop' function
        await asyncio.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    # Generate fixed outputs to test if the function has been called
    async def mock_manager_apply(self, inv_chunks):
        self.mock_inv_chunks = inv_chunks

    async def mock_manager_run(self):
        self.mock_mng_run = True

    async def mock_launch_with_dir(self):
        self.mock_launched = True

    # test usual run function behaviour
    args = default_args
    c = generate_controller(args=args, inv_file=inv_file)
    with patch.object(c, '_stop', MagicMock(side_effect=c._stop)) as stop_mock:
        with patch.multiple(SqNativeFile, set_device=mock_native_set_device):
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
                    assert hasattr(c.manager, 'mock_mng_run'), \
                        'manager.run was not called'

                    # check duplicated are removed
                    assert c.manager.mock_inv_chunks == [netbox_inventory]

                    stop_mock.assert_called()

    # test with input-dir argument
    args = default_args
    args['run_once'] = True
    args['input_dir'] = 'tests/unit/poller/controller/data/'

    c = generate_controller(args=args, inv_file=inv_file)
    c.init()
    with patch.multiple(StaticManager, launch_with_dir=mock_launch_with_dir,
                        run=mock_manager_run):
        await c.run()
        assert hasattr(c.manager, 'mock_launched'), \
            'manager.launch_with_dir was not called'
        assert hasattr(c.manager, 'mock_mng_run'), \
            'manager.run was not called'


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
def test_controller_init_errors(inv_file: str, mock_plugins,
                                default_args):
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

    c = generate_controller(args=default_args, inv_file=inv_file)

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
async def test_controller_empty_inventory(inv_file: str, mock_plugins,
                                          default_args):
    """Test that the controller launches an exception with an
    empty global inventory

    Args:
        inv_file (str): inventory file
    """

    def mock_set_device(self):
        self.mocked_inv = {}

    c = generate_controller(args=default_args, inv_file=inv_file)

    with patch.multiple(SqNativeFile, set_device=mock_set_device, name='n'):
        with patch.multiple(Netbox, set_device=mock_set_device, name='n'):
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
                                            mock_plugins, default_args):
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

    c = generate_controller(default_args, inv_file, config_file)
    c.init()
    with patch.multiple(Netbox, run=mock_netbox_run, name='n'):
        with pytest.raises(InventorySourceError):
            await c.run()
