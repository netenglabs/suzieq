"""
ServiceManager component unit tests
"""
import asyncio
import os
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest
from suzieq.poller.worker.services.service import Service
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.shared.exceptions import SqPollerConfError
from tests.conftest import _get_async_task_mock, suzieq_test_svc_dir

SERVICE_DIR = './suzieq/config'
SCHEMA_DIR = f'{SERVICE_DIR}/schema'


def _get_services():
    """Get the entire list of available services
    """
    svcs = list(Path(SERVICE_DIR).glob('*.yml'))
    all_svcs = [os.path.basename(x).split('.')[0] for x in svcs]
    return all_svcs


def _init_service_manager(add_tasks: Callable = None,
                          svc_dir: str = SERVICE_DIR,
                          schema_dir: str = SCHEMA_DIR,
                          queue: asyncio.Queue = asyncio.Queue,
                          run_mode: str = 'forever',
                          interval: int = 30,
                          service_only: str = None,
                          exclude_svcs: str = None):
    # Create add tasks method mock
    if not add_tasks:
        add_tasks = _get_async_task_mock()

    # Construct additional parameters
    other_params = {}
    if service_only:
        other_params['service_only'] = service_only
    if exclude_svcs:
        other_params['exclude_services'] = exclude_svcs

    # Init ServiceManager
    return ServiceManager(add_tasks,
                          svc_dir,
                          schema_dir,
                          queue,
                          run_mode,
                          interval,
                          **other_params)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
def test_init_service_manager():
    """Test correct ServiceManager initialization
    """
    run_mode = 'forever'
    interval = 30
    add_tasks = _get_async_task_mock()
    service_manager = ServiceManager(add_tasks,
                                     SERVICE_DIR,
                                     SCHEMA_DIR,
                                     asyncio.Queue(),
                                     run_mode,
                                     interval)
    # Check if the service manager has been correctly initialized
    assert service_manager.add_task_fn == add_tasks
    assert service_manager.service_directory == SERVICE_DIR
    assert service_manager.schema_dir == SCHEMA_DIR
    assert service_manager.output_queue
    assert service_manager.default_interval == 30
    assert service_manager.run_mode == run_mode

    # Check the list of services
    assert set(service_manager.svcs_list) == set(_get_services())


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
def test_wrong_service_dir():
    """Test a wrong service and schema directories
    """
    # Test wrong service directory
    with pytest.raises(SqPollerConfError):
        _init_service_manager(svc_dir='wrong/dir')

    # Test wrong schema directory
    with pytest.raises(SqPollerConfError):
        _init_service_manager(schema_dir='wrong/dir')


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
def test_svcslist_contruction():
    """Test the construction of the service list
    """
    # Test construction of service list with only some services
    service_only = 'arpnd bgp'
    svc_mgr = _init_service_manager(service_only=service_only)
    assert set(svc_mgr.svcs_list) == set(service_only.split())
    # Check for no duplicates
    assert len(set(svc_mgr.svcs_list)) == len(svc_mgr.svcs_list)

    # Test service removal
    no_services = 'bgp interfaces'
    svc_mgr = _init_service_manager(exclude_svcs=no_services)
    expected = set(filter(lambda x: x not in no_services.split(),
                          _get_services()))
    assert set(expected) == set(svc_mgr.svcs_list)
    # Check for no duplicates
    assert len(set(svc_mgr.svcs_list)) == len(svc_mgr.svcs_list)

    # Test both service only and removal
    service_only = 'bgp arpnd interfaces'
    no_services = 'bgp'
    expected = set(filter(lambda x: x not in no_services.split(),
                          service_only.split()))
    svc_mgr = _init_service_manager(service_only=service_only,
                                    exclude_svcs=no_services)
    assert set(expected) == set(svc_mgr.svcs_list)
    # Check for no duplicates
    assert len(set(svc_mgr.svcs_list)) == len(svc_mgr.svcs_list)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
def test_wrong_svcslist_contruction():
    """Test service construction with invalid service name
    """
    invalid_services = 'invalid notvalid'

    # Invalid service name in service_only
    with pytest.raises(SqPollerConfError):
        _init_service_manager(service_only=invalid_services)

    # Invalid service name in exclude_services
    with pytest.raises(SqPollerConfError):
        _init_service_manager(exclude_svcs=invalid_services)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
@pytest.mark.asyncio
async def test_service_init():
    """Test service initialization
    """
    svc_mgr = _init_service_manager()
    services = await svc_mgr.init_services()
    # Check if something have been returned
    assert services

    # Check if services have been internally set
    assert services == svc_mgr.services

    # Check if all the services in the list have been intialized
    initialized = [s.name for s in services]
    initialized_set = set(initialized)
    assert initialized_set == set(_get_services())

    # Check if there are duplicated services
    assert len(initialized) == len(initialized_set)

    # Check if the running mode is the correct one
    assert all([s.run_once == svc_mgr.run_mode for s in services])


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
@pytest.mark.asyncio
async def test_service_init_service_only():
    """Check if only the selected services are initialized
    """
    service_only = "arpnd interfaces"
    svc_mgr = _init_service_manager(service_only=service_only)
    services = await svc_mgr.init_services()
    # Check if something have been returned
    assert len(services) == 2
    # Check if the service is 'valid'
    assert all(s.name in service_only.split() for s in services)
    assert services[0].name != services[1].name


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
@pytest.mark.asyncio
async def test_service_init_wrong_files():
    """Test invalid service files:
    - Missing 'service' or 'apply' keyword
    - Missing schema
    - Copy with wrong reference
    Only a service is expected to be valid
    """

    service_only = ('missing_schema missing_apply '
                    'wrong_copy valid missing_service')
    svc_mgr = _init_service_manager(svc_dir=suzieq_test_svc_dir,
                                    schema_dir=f'{suzieq_test_svc_dir}/schema',
                                    service_only=service_only)
    services = await svc_mgr.init_services()
    # Check if something have been returned
    assert len(services) == 1
    # Check if the service is 'valid'
    assert services[0].name == 'valid'


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
@pytest.mark.asyncio
async def test_service_scheduling():
    """Test scheduling of the services tasks
    """
    # Mock service run
    run_res = asyncio.Future()
    run_res.set_result(None)

    svc_mgr = _init_service_manager()
    await svc_mgr.init_services()
    # schedule the services
    with patch.object(Service, 'run', return_value=run_res):
        await svc_mgr.schedule_services_run()

    # Check if add tasks have been called
    svc_mgr.add_task_fn.assert_called()
    # Check if there are running tasks
    assert svc_mgr.running_services
    assert len(svc_mgr.running_services) == len(svc_mgr.svcs_list)
    # Suppress never awaited alert
    await asyncio.wait([asyncio.create_task(s)
                        for s in svc_mgr.running_services])


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.service_manager
@pytest.mark.asyncio
async def test_set_nodes():
    """Check if the nodes are correctly set in all the services
    """
    node_list = {
        'host1.default': {
            'hostname': 'host1',
            'postq': None
        }
    }
    svc_mgr = _init_service_manager()
    await svc_mgr.init_services()
    await svc_mgr.set_nodes(node_list)
    # Check if all the nodes have the inventory set
    assert all(s.node_postcall_list == node_list for s in svc_mgr.services)
