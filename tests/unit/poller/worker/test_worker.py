"""
Poller component unit tests
"""
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import argparse
import asyncio
import os
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
from suzieq.poller.worker.inventory.inventory import Inventory
from suzieq.poller.worker.worker import Worker
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.poller.worker.writers.output_worker_manager import \
    OutputWorkerManager
from suzieq.shared.exceptions import SqPollerConfError
from suzieq.shared.utils import load_sq_config
from tests.conftest import get_async_task_mock, create_dummy_config_file

INVENTORY_PATH = 'tests/unit/poller/worker/utils/dummy_inventory'
INV_CREDENTIAL_KEY = 'dummy_key'


@pytest.fixture
def poller_args(monkeypatch):
    """Generate a config file and some standard
    user arguments
    """
    # Set two enviroment variable containing the path to a dummy inventory
    # and a dummy key for credential decryption
    monkeypatch.setenv('SQ_CONTROLLER_POLLER_CRED', INV_CREDENTIAL_KEY)
    monkeypatch.setenv('SQ_INVENTORY_PATH', INVENTORY_PATH)
    cfg_file = create_dummy_config_file()
    userargs_dict = {
        'namespace': None,
        'input_dir': None,
        'service_only': None,
        'exclude_services': None,
        'outputs': ['parquet'],
        'output_dir': 'tests/unit/poller/worker/poller_output/parquet_out',
        'config': cfg_file,
        'run_once': None,
        'ssh_config_file': None,
        'worker_id': '0'
    }
    userargs = argparse.Namespace(**userargs_dict)
    yield userargs
    os.remove(cfg_file)


async def run_worker_with_mocks(poller: Worker) -> Dict[str, MagicMock]:
    """Run the poller replacing component 'run' functions with mocks
    """

    # Create a mock for each method
    mks = {
        'inventory': get_async_task_mock(),
        'service_manager': get_async_task_mock(),
        'output_worker_manager': get_async_task_mock()
    }

    with patch.multiple(Inventory,
                        schedule_nodes_run=mks['inventory']), \
        patch.multiple(ServiceManager,
                       schedule_services_run=mks['service_manager']), \
        patch.multiple(OutputWorkerManager,
                       run_output_workers=mks['output_worker_manager']), \
        patch.multiple(asyncio,
                       get_event_loop=MagicMock()):
        poller_run = asyncio.create_task(poller.run())
        await asyncio.wait([poller_run])
    return mks


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_object
def test_worker_object_init_validation(poller_args):
    """Test Poller object user_args validation
    """
    cfg = load_sq_config(config_file=poller_args.config)

    # Test invalid ssh config file
    poller_args.ssh_config_file = 'invalid'
    with pytest.raises(SqPollerConfError):
        Worker(poller_args, cfg)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_object
@pytest.mark.asyncio
async def test_add_pop_worker_task(poller_args):
    """Test the methods for adding and removing the poller tasks
    """
    cfg = load_sq_config(config_file=poller_args.config)
    poller = Worker(poller_args, cfg)
    # Test add_poller_task()
    tasks = [asyncio.Future(), asyncio.Future()]
    await poller._add_worker_tasks(tasks)
    assert poller.waiting_tasks == tasks
    # Test _pop_waiting_poller_tasks()
    received = await poller._pop_waiting_worker_tasks()

    # Check if there aren't poller tasks
    assert not poller.waiting_tasks

    # Check if the received tasks are the expected ones
    assert received == tasks


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_object
@pytest.mark.asyncio
async def test_poller_worker_run(poller_args):
    """Check if all the services are launched after calling Poller.run()
    """
    cfg = load_sq_config(config_file=poller_args.config)
    poller = Worker(poller_args, cfg)

    mks = await run_worker_with_mocks(poller)
    # Check if all the functions have been called
    for mk in mks:
        mks[mk].assert_called()


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_object
def test_worker_inventory_init(poller_args):
    """Test if all the parameters are correctly passed to the Inventory
    """
    cfg = load_sq_config(config_file=poller_args.config)
    poller_args.ssh_config_file = 'config/file'
    cfg['poller']['connect-timeout'] = 30
    with patch.multiple(Worker, _validate_worker_args=MagicMock()):
        poller = Worker(poller_args, cfg)

    inv = poller.inventory
    # Check if all the values are valid
    assert inv.ssh_config_file == poller_args.ssh_config_file
    assert inv.connect_timeout == cfg['poller']['connect-timeout']


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_object
def test_worker_inventory_init_addnl_args(poller_args):
    """Test if all the additional params are actually passed to the
    Inventory class init function
    """
    cfg = load_sq_config(config_file=poller_args.config)
    poller_args.ssh_config_file = 'config/file'
    cfg['poller']['connect-timeout'] = 30
    dummy_inventory_class = MagicMock()
    dummy_get_classes = MagicMock(
        return_value={Worker.DEFAULT_INVENTORY: dummy_inventory_class}
    )
    with patch.multiple(Worker, _validate_worker_args=MagicMock(),
                        _init_inventory=MagicMock()):
        poller = Worker(poller_args, cfg)

    # Init the inventory with additional parameters
    addnl_args = {
        'test_1': 1,
        'test_2': 2
    }
    with patch.multiple(Worker, _get_inventory_plugins=dummy_get_classes):
        poller._init_inventory(poller_args, cfg, addnl_args)

    # Check if the Inventory have been initiliazed
    dummy_inventory_class.assert_called()

    # Check if the additional params have been provided
    provided_args = dummy_inventory_class.call_args_list[0][1]

    assert addnl_args.items() <= provided_args.items(), \
        'Additional arguments not provided to the Inventory class init'

    # Check that even the other parameters are provided
    inventory_args = {
        'connect_timeout': cfg['poller']['connect-timeout'],
        'ssh_config_file': poller_args.ssh_config_file
    }
    assert inventory_args.items() <= provided_args.items(), \
        'Additional args provided but the others were not provided'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_object
def test_worker_service_manager_init(poller_args):
    """Test if all the parameters are correctly passed to the ServiceManager
    """
    cfg = load_sq_config(config_file=poller_args.config)
    poller_args.run_once = 'gather'
    cfg['poller']['period'] = 30
    poller = Worker(poller_args, cfg)

    mgr = poller.service_manager
    # Check if all the values are valid
    assert mgr.service_directory == cfg['service-directory']
    assert mgr.schema_dir == cfg['schema-directory']
    assert mgr.default_interval == cfg['poller']['period']
    assert mgr.run_mode == poller_args.run_once
