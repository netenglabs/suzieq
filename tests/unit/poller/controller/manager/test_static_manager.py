"""This module contains the tests to for the poller controller static manager
"""
# pylint: disable=dangerous-default-value
# pylint: disable=consider-using-enumerate
# pylint: disable=redefined-outer-name

import asyncio
import os
from contextlib import suppress
from pathlib import Path
from typing import Dict, List, Tuple
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
import pytest
import yaml
import suzieq.poller.controller.manager.static as static_manager_module
from suzieq.poller.controller.manager.static import StaticManager
from suzieq.shared.exceptions import PollingError
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file, get_async_task_mock
from tests.unit.poller.shared.utils import get_random_node_list

MANAGER_ARGS = {
    'debug': False,
    'input-dir': None,
    'exclude-services': None,
    'no-coalescer': False,
    'output-dir': '/tmp/out-dir',
    'outputs': ['parquet', 'gather'],
    'run-once': None,
    'single-run-mode': None,
    'service-only': None,
    'ssh-config-file': None,
    'workers': 1
}


@pytest.fixture
def manager_cfg():
    """Get a dummy configuration file
    """
    args = {}
    args['config'] = create_dummy_config_file()
    args['config-dict'] = load_sq_config(config_file=args['config'])
    yield args
    os.remove(args['config'])


class DummyCoalescerLauncher:
    """A dummy CoalescerLaucher to use as mock
    """

    def __init__(self) -> None:
        self.fut = asyncio.Future()
        self.monitor_called = False

    async def start_and_monitor_coalescer(self):
        """Simulate the coalescer monitoring
        """
        self.monitor_called = True
        await self.fut


async def apply_with_mocks(manager: StaticManager,
                           chunks: List[Dict]) -> Tuple[MagicMock, MagicMock]:
    """Apply the chunks with mocks preventing the application to actually
    start the workers

    Args:
        manager (StaticManager): the static manager to use
        chunks (List[Dict]): the chunks to apply to each of the worker

    Returns:
        Tuple[MagicMock, MagicMock]: the MagicMocks representing the function
            to start and stop the workers
    """
    launch_fn = get_async_task_mock()
    stop_fn = get_async_task_mock()
    write_chunk_fn = get_async_task_mock()
    with patch.multiple(StaticManager,
                        _launch_poller=launch_fn,
                        _stop_poller=stop_fn,
                        _write_chunk=write_chunk_fn):
        await manager.apply(chunks)
    return launch_fn, stop_fn, write_chunk_fn


async def dummy_monitor_process(process: MagicMock, _):
    """A dummy function simulating the process monitoring

    Args:
        process (MagicMock): a MagicMock representing the process
        _ (str): the name of the tasl. Not used.
    """
    await process.fut


def get_fake_process(fut: asyncio.Future, returncode: int = 0) -> MagicMock:
    """Generate a fake process with a MagicMock

    Args:
        fut (asyncio.Future): the future to assign to the process
        returncode (int, optional): The return code of the process.
            Defaults to 0.

    Returns:
        MagicMock: the fake process
    """
    fake_process = MagicMock()
    fake_process.fut = fut
    fake_process.returncode = returncode
    return fake_process


def init_static_manager(manager_cfg: Dict,
                        args: Dict = MANAGER_ARGS) -> StaticManager:
    """Init the static manager
    """
    args.update(manager_cfg)

    return StaticManager(args)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.parametrize("max_outstanding_cmds", [0, 5])
def test_static_manager_init(monkeypatch, manager_cfg, max_outstanding_cmds):
    """Test the initialization of the static manager
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)
    manager_args = MANAGER_ARGS.copy()
    manager_args['exclude-services'] = ['arpn']
    manager_args['service-only'] = ['interfaces', 'ospf']
    manager_args['ssh-config-file'] = 'ssh_config_file'
    manager_args['max-cmd-pipeline'] = max_outstanding_cmds

    # Init manager
    static_manager = init_static_manager(manager_cfg, manager_args)

    # Check if the evironment variables have been set
    assert fake_environ.get('SQ_CONTROLLER_POLLER_CRED'), \
        'Credential file decryption key not set in environment'
    assert fake_environ.get('SQ_INVENTORY_PATH'), \
        'Inventory path not set in environment'
    assert Path(fake_environ['SQ_INVENTORY_PATH']).exists(), \
        'Inventory path not correctly created'

    # Check if the proper value of max outstanding commands is provided
    max_cmds_env = fake_environ.get('SQ_MAX_OUTSTANDING_CMD')
    expected_max_cmds = (str(max_outstanding_cmds)
                         if max_outstanding_cmds
                         else None)
    assert max_cmds_env == expected_max_cmds, \
        'The value of max outstanding commands is not the expected one'

    # Check if the parameters construction is valid
    allowed_args = ['run-once', 'exclude-services',
                    'outputs', 'output-dir', 'service-only',
                    'ssh-config-file', 'config', 'input-dir']

    obt_values = static_manager._args_to_pass[1:]
    for i in range(len(obt_values)):
        arg = obt_values[i]
        if isinstance(arg, str) and arg[0] == '-':
            arg_name = arg[2:]
            assert arg_name in allowed_args, \
                f'{arg_name} is not allowed as poller worker argument'
            expected_val = manager_args[arg_name]
            if isinstance(expected_val, list):
                # Check if the list of args is long enough
                expected_val_len = len(expected_val)
                assert len(obt_values) - 1 >= i + expected_val_len, \
                    f'The list of args has not enough arguments for {arg}'
                obtained_set = set(obt_values[i + 1: i + expected_val_len + 1])
                assert set(expected_val) == obtained_set
                i += expected_val_len
            else:
                assert len(obt_values) - 1 >= i + 1
                assert expected_val == obt_values[i + 1]
                i += 1

    # Check the remaining attributes
    assert static_manager._no_coalescer == manager_args['no-coalescer']


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_inventory_apply(monkeypatch, manager_cfg):
    """Check if the inventory is correctly applied
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager = init_static_manager(manager_cfg)
    _, _, inventory = get_random_node_list(20)

    launch_fn, stop_fn, \
        write_chunk_fn = await apply_with_mocks(manager, [inventory])

    # Check if poller have been correctly called
    launch_fn.assert_called_once_with(0)
    write_chunk_fn.assert_called_once_with(0, inventory)
    stop_fn.assert_not_called()


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_inventory_changes_apply(monkeypatch, manager_cfg):
    """Check if the inventory is correctly applied
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager_args = MANAGER_ARGS.copy()
    manager_args['workers'] = 3
    manager = init_static_manager(manager_cfg, manager_args)

    _, _, chunk1 = get_random_node_list(20)
    _, _, chunk2 = get_random_node_list(20)
    _, _, chunk3 = get_random_node_list(20)

    inventory = [chunk1, chunk2, chunk3]
    launch_fn, stop_fn, \
        write_chunk_fn = await apply_with_mocks(manager, inventory)

    # Check if poller have been correctly called
    for i, c in enumerate(inventory):
        launch_fn.assert_any_call(i)
        write_chunk_fn.assert_any_call(i, c)
    stop_fn.assert_not_called()

    # Test no changes
    inventory = [chunk1, chunk2, chunk3]
    launch_fn, stop_fn, \
        write_chunk_fn = await apply_with_mocks(manager, inventory)
    launch_fn.assert_not_called()
    stop_fn.assert_not_called()
    write_chunk_fn.assert_not_called()

    # Completely change last two chunks
    _, _, chunk2 = get_random_node_list(20)
    _, _, chunk3 = get_random_node_list(20)
    inventory = [chunk1, chunk2, chunk3]
    launch_fn, stop_fn, \
        write_chunk_fn = await apply_with_mocks(manager, inventory)

    for i in range(1, 2):
        launch_fn.assert_any_call(i)
        stop_fn.assert_any_call(i)
        write_chunk_fn.assert_any_call(i, inventory[i])

    # Minor changes to one chunk
    to_change_key = list(chunk2.keys())[0]
    chunk2[to_change_key]['address'] = '10.0.0.1'
    inventory = [chunk1, chunk2, chunk3]
    launch_fn, stop_fn, \
        write_chunk_fn = await apply_with_mocks(manager, inventory)

    launch_fn.assert_any_call(1)
    stop_fn.assert_any_call(1)
    write_chunk_fn.assert_any_call(1, inventory[1])

    # All chunks change
    _, _, chunk1 = get_random_node_list(20)
    _, _, chunk2 = get_random_node_list(20)
    _, _, chunk3 = get_random_node_list(20)

    inventory = [chunk1, chunk2, chunk3]
    launch_fn, stop_fn, \
        write_chunk_fn = await apply_with_mocks(manager, inventory)

    for i, c in enumerate(inventory):
        launch_fn.assert_any_call(i)
        stop_fn.assert_any_call(i)
        write_chunk_fn.assert_any_call(i, c)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_apply_inventory_wrong_chunk_number(monkeypatch, manager_cfg):
    """Apply an inventory with a wrong number of chunk
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager = init_static_manager(manager_cfg)

    inventory = [{} for _ in range(3)]

    with pytest.raises(PollingError, match=r'The number of chunks is *'):
        await apply_with_mocks(manager, inventory)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_launch_debug_mode(monkeypatch, manager_cfg, capsys):
    """Test the debug mode, check if no worker is launched and if the help
    message have been printed
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager_args = MANAGER_ARGS.copy()
    manager_args['single-run-mode'] = 'debug'
    manager_args['workers'] = 2
    manager = init_static_manager(manager_cfg, manager_args)

    _, _, chunk1 = get_random_node_list(1)
    _, _, chunk2 = get_random_node_list(1)
    inventory = [chunk1, chunk2]

    launch_fn, stop_fn, \
        write_chunk_fn = await apply_with_mocks(manager, inventory)

    # Check if no worker has been launched
    launch_fn.assert_not_called()
    stop_fn.assert_not_called()

    # Check if chunks have been written
    for i, c in enumerate(inventory):
        write_chunk_fn.assert_any_call(i, c)

    help_message = capsys.readouterr().out
    # Make sure an output have been returned
    assert help_message, 'No help message printed'
    worker_messages = help_message.split('\n\n')

    # Check if the number of messages is equal to the number of workers
    expected_lines = manager_args['workers']
    # We need to remove the very first line
    obtained_lines = len(worker_messages) - 1
    assert expected_lines == obtained_lines, \
        f"Expected {expected_lines} commands, {obtained_lines} obtained"


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_launch_debug_mode_input_dir(monkeypatch, manager_cfg, capsys):
    """Test the debug mode with the input directory
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager_args = MANAGER_ARGS.copy()
    manager_args['single-run-mode'] = 'debug'
    manager_args['input-dir'] = 'tests/'
    manager = init_static_manager(manager_cfg, manager_args)

    launch_fn = get_async_task_mock()
    with patch.multiple(StaticManager,
                        _launch_poller=launch_fn):
        await manager.launch_with_dir()

    # Check if no worker has been launched
    launch_fn.assert_not_called()

    # Check that no inventory have been written
    assert not hasattr(manager, '_inventory_path'), \
        'The inventory path is set but not inventory should be written'

    help_message = capsys.readouterr().out
    # Make sure an output have been returned
    assert help_message, 'No help message printed'
    worker_messages = help_message.split('\n\n')

    assert len(worker_messages) == 2, 'Expected help message with 2 lines'

    # Check if the input directory is in the arguments
    command_line = worker_messages[1]
    assert '-i' in command_line, '-i flag not present'
    assert manager_args['input-dir'] in command_line


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_launch_with_input_dir(monkeypatch, manager_cfg):
    """Test the debug mode with the input directory
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager_args = MANAGER_ARGS.copy()
    manager_args['single-run-mode'] = 'input-dir'
    manager_args['input-dir'] = 'tests/'
    manager = init_static_manager(manager_cfg, manager_args)

    launch_fn = get_async_task_mock()
    with patch.multiple(StaticManager,
                        _launch_poller=launch_fn):
        await manager.launch_with_dir()

    # Check if the worker have been called
    launch_fn.assert_called_once()
    launch_fn.assert_any_call(0)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_exception_when_launching_worker(monkeypatch, manager_cfg):
    """Test if exception when launching the workers is properly handled
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager = init_static_manager(manager_cfg)

    write_chunk_fn = get_async_task_mock()
    launch_res = asyncio.Future()
    launch_res.set_exception(Exception('test'))
    launch_fn = MagicMock(return_value=launch_res)

    _, _, chunk1 = get_random_node_list(1)

    with pytest.raises(Exception, match=r'test'):
        with patch.multiple(StaticManager, _launch_poller=launch_fn,
                            _write_chunk=write_chunk_fn):
            await manager.apply([chunk1])


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_write_chunk(monkeypatch, manager_cfg):
    """Test the creation of the inventory files
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    devices, credentials, chunk1 = get_random_node_list(20)
    manager = init_static_manager(manager_cfg)

    # Write the chunks
    await manager._write_chunk(0, chunk1)

    # Check if something have been written
    inventory_dir = manager._inventory_path
    inventory_path = inventory_dir / f'{manager._inventory_file_name}_0.yml'
    credentials_path = inventory_dir / 'cred_0'

    # Check if files have been created
    assert inventory_path.exists(), "Inventory file not created"
    assert credentials_path.exists(), "Credentials file not created"

    # Read the file content
    # Assert the devices list is the expected one
    with open(str(inventory_path), "r") as out_file:
        inventory_data = out_file.read()
        obtained_inventory = yaml.safe_load(inventory_data)

    assert obtained_inventory == devices, \
        'Device part of the inventory do not match'

    # Assert the credentials are the expexted ones
    with open(credentials_path, "r") as out_file:
        cred_enc_data = out_file.read()

    cred_key = fake_environ['SQ_CONTROLLER_POLLER_CRED'].encode('utf-8')
    decryptor = Fernet(cred_key)
    # Decrypt the credentials
    cred_data = decryptor.decrypt(cred_enc_data.encode('utf-8'))
    obtained_credentials = yaml.safe_load(cred_data)
    assert obtained_credentials == credentials, \
        'Credentials part of the inventory do not match'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_launch_worker(monkeypatch, manager_cfg):
    """Test the creation of the worker process
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager = init_static_manager(manager_cfg)
    fake_process = MagicMock()
    create_subprocess_fn = get_async_task_mock(fake_process)
    with patch.multiple(asyncio, create_subprocess_exec=create_subprocess_fn):
        expected_worker_id = 1
        await manager._launch_poller(expected_worker_id)
        # Check if the process have been correctly created
        create_subprocess_fn.assert_called()
        assert manager._waiting_workers.get(expected_worker_id), \
            'Worker not placed in the waiting queue'
        assert manager._waiting_workers[expected_worker_id] == fake_process, \
            'The worker process is not the expected one'

        # Check the arguments passed to the worker
        call_args = list(list(create_subprocess_fn.call_args_list[0])[0])
        try:
            worker_id_index = call_args.index('--worker-id') + 1
        except ValueError:
            pytest.fail('Worker id flag not provided')
        assert len(call_args) > worker_id_index, \
            'Worker id value not provided to worker'
        assert call_args[worker_id_index] == str(expected_worker_id)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_launch_worker_process_creation_fails(monkeypatch, manager_cfg):
    """Test if an exception is raised if it is not possible to create the
    poller worker process.
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager = init_static_manager(manager_cfg)
    create_subprocess_fn = get_async_task_mock()
    with patch.multiple(asyncio, create_subprocess_exec=create_subprocess_fn):
        expected_worker_id = 1
        with pytest.raises(PollingError):
            await manager._launch_poller(expected_worker_id)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_worker_replace(monkeypatch, manager_cfg):
    """Test if execute is able to handle a worker replaced by another
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager = init_static_manager(manager_cfg)

    coalescer_monitor_mock = DummyCoalescerLauncher()

    with patch.multiple(static_manager_module,
                        monitor_process=dummy_monitor_process), \
            patch.object(manager, '_coalescer_launcher',
                         coalescer_monitor_mock):
        execute_task = asyncio.create_task(manager._execute())
        try:
            injected_workers = {
                0: asyncio.Future(),
                1: asyncio.Future()
            }
            manager._waiting_workers[0] = get_fake_process(injected_workers[0])
            manager._waiting_workers[1] = get_fake_process(injected_workers[1])

            manager._poller_tasks_ready.set()
            # Sleep for the workers being monitored
            await asyncio.sleep(0.1)

            # Check if the coalescer started
            assert coalescer_monitor_mock.monitor_called, \
                'Coalescer not launched'

            # Replace one of the workers
            manager._poller_tasks_ready.clear()
            injected_workers[1].set_result(None)
            injected_workers[1] = asyncio.Future()

            manager._waiting_workers[1] = get_fake_process(injected_workers[1])
            manager._poller_tasks_ready.set()
            await asyncio.sleep(0.1)

            # Check if the waiting workers have been monitored
            assert not manager._waiting_workers, 'New worker not monitored'

            # Check if the execute task is running
            if execute_task.done():
                exc = execute_task.exception()
                if exc:
                    raise exc
                pytest.fail(
                    'Unexpected _execute task termination without exceptions')
        finally:
            # Cancel the execute task
            execute_task.cancel()
            with suppress(asyncio.CancelledError):
                await execute_task
            # Resolve all the futures to suppress any warning
            if injected_workers:
                pending_tasks = [i for i in injected_workers.values()
                                 if not i.done()]
                for i in pending_tasks:
                    i.set_result(None)
            coalescer_monitor_mock.fut.set_result(None)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_unexpected_worker_death(monkeypatch, manager_cfg):
    """Test if an exception is raised when there is an unexpected worker death
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)

    manager = init_static_manager(manager_cfg)

    coalescer_monitor_mock = DummyCoalescerLauncher()

    with patch.multiple(static_manager_module,
                        monitor_process=dummy_monitor_process), \
            patch.object(manager, '_coalescer_launcher',
                         coalescer_monitor_mock):
        execute_task = asyncio.create_task(manager._execute())

        try:
            injected_workers = {
                0: asyncio.Future(),
                1: asyncio.Future()
            }
            manager._waiting_workers[0] = get_fake_process(injected_workers[0])
            manager._waiting_workers[1] = get_fake_process(
                injected_workers[1], 1)

            manager._poller_tasks_ready.set()
            # Sleep for the workers being monitored
            await asyncio.sleep(0.1)
            injected_workers[1].set_result(None)
            with pytest.raises(PollingError,
                               match='Unexpected worker 1 death:.*'):
                await asyncio.wait_for(execute_task, 2)
        finally:
            # Cancel the execute task
            if not execute_task.done():
                execute_task.cancel()
                with suppress(asyncio.CancelledError):
                    await execute_task

            # Resolve all the promises to suppress all the warnings
            if injected_workers:
                pending_tasks = [i for i in injected_workers.values()
                                 if not i.done()]
                for i in pending_tasks:
                    i.set_result(None)
            coalescer_monitor_mock.fut.set_result(None)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.controller
@pytest.mark.controller_manager
@pytest.mark.controller_manager_static
@pytest.mark.asyncio
async def test_execute_run_once(monkeypatch, manager_cfg):
    """Test if no exceptions and the coalescer is not launched when 'run_once'
    mode is active
    """
    fake_environ = {}
    monkeypatch.setattr(os, 'environ', fake_environ)
    manager_args = MANAGER_ARGS.copy()
    manager_args['run-once'] = 'gather'
    manager_args['single-run-mode'] = manager_args['run-once']
    manager_args['no-coalescer'] = True

    manager = init_static_manager(manager_cfg, manager_args)

    assert not getattr(manager, '_coalescer_launcher', None), \
        'Coalescer launcher initialized with run once mode'

    with patch.multiple(static_manager_module,
                        monitor_process=dummy_monitor_process):
        execute_task = asyncio.create_task(manager._execute())

        try:
            injected_worker = asyncio.Future()
            manager._waiting_workers[0] = get_fake_process(injected_worker)

            manager._poller_tasks_ready.set()
            # Sleep for the workers being monitored
            await asyncio.sleep(0.1)

            injected_worker.set_result(None)
            await asyncio.sleep(0.1)

            # Check if the execute task properly terminated
            assert execute_task.done()
            assert not execute_task.exception(), \
                f'Manager terminated with exception {execute_task.exception()}'
        finally:
            # Cancel the execute task
            if not execute_task.done():
                execute_task.cancel()
                with suppress(asyncio.CancelledError):
                    await execute_task

            # Resolve all the promises to suppress all the warnings
            if injected_worker and not injected_worker.done():
                injected_worker.set_result(None)
