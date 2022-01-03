"""
Poller component unit tests
"""
# pylint: disable=redefined-outer-name
# pylint: disable=unsubscriptable-object
# pylint: disable=protected-access

import argparse
import asyncio
import os
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
from suzieq.poller.worker.coalescer_launcher import CoalescerLauncher
from suzieq.poller.worker.inventory.inventory import Inventory
from suzieq.poller.worker.poller import Poller
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.poller.worker.writers.output_worker_manager import OutputWorkerManager
from suzieq.shared.exceptions import SqPollerConfError
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file, _get_async_task_mock


@pytest.fixture
def poller_args():
    """Generate a config file and some standard
    user arguments
    """
    # Set an environment variable with a dummy key for credential file
    # decryption
    os.environ['SQ_CONTROLLER_POLLER_CRED'] = 'test'
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


async def run_poller_with_mocks(poller: Poller) -> Dict[str, MagicMock]:
    """Run the poller replacing component 'run' functions with mocks
    """

    # Create a mock for each method
    mks = {
        'inventory': _get_async_task_mock(),
        'service_manager': _get_async_task_mock(),
        'output_worker_manager': _get_async_task_mock()
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
@pytest.mark.poller_object
def test_poller_object_init_validation(poller_args):
    """Test Poller object user_args validation
    """
    cfg = load_sq_config(poller_args.config)

    # Test invalid ssh config file
    poller_args.ssh_config_file = 'invalid'
    with pytest.raises(SqPollerConfError):
        Poller(poller_args, cfg)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_object
@pytest.mark.asyncio
async def test_add_pop_poller_task(poller_args):
    """Test the methods for adding and removing the poller tasks
    """
    cfg = load_sq_config(poller_args.config)
    poller = Poller(poller_args, cfg)
    # Test add_poller_task()
    tasks = [asyncio.Future(), asyncio.Future()]
    await poller._add_poller_task(tasks)
    assert poller.waiting_tasks == tasks
    # Test _pop_waiting_poller_tasks()
    received = await poller._pop_waiting_poller_tasks()

    # Check if there aren't poller tasks
    assert not poller.waiting_tasks

    # Check if the received tasks are the expected ones
    assert received == tasks


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_object
@pytest.mark.asyncio
async def test_poller_run(poller_args):
    """Check if all the services are launched after calling Poller.run()
    """
    cfg = load_sq_config(poller_args.config)
    poller = Poller(poller_args, cfg)

    mks = await run_poller_with_mocks(poller)
    # Check if all the functions have been called
    for mk in mks:
        mks[mk].assert_called()

@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_object
def test_poller_inventory_init(poller_args):
    """Test if all the parameters are correctly passed to the Inventory
    """
    cfg = load_sq_config(poller_args.config)
    poller_args.ssh_config_file = 'config/file'
    cfg['poller']['connect-timeout'] = 30
    with patch.multiple(Poller, _validate_poller_args=MagicMock()):
        poller = Poller(poller_args, cfg)

    inv = poller.inventory
    # Check if all the values are valid
    assert inv.ssh_config_file == poller_args.ssh_config_file
    assert inv.connect_timeout == cfg['poller']['connect-timeout']


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_object
def test_poller_service_manager_init(poller_args):
    """Test if all the parameters are correctly passed to the ServiceManager
    """
    cfg = load_sq_config(poller_args.config)
    poller_args.run_once = 'gather'
    cfg['poller']['period'] = 30
    poller = Poller(poller_args, cfg)

    mgr = poller.service_manager
    # Check if all the values are valid
    assert mgr.service_directory == cfg['service-directory']
    assert mgr.schema_dir == cfg['schema-directory']
    assert mgr.default_interval == cfg['poller']['period']
    assert mgr.run_mode == poller_args.run_once
