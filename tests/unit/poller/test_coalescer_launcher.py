"""
Test the CoalescerLauncher component
"""
# pylint: disable=redefined-outer-name

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
import suzieq.poller.worker.coalescer_launcher as coalescer_launcher_module
from suzieq.poller.worker.coalescer_launcher import CoalescerLauncher
from suzieq.shared.exceptions import PollingError
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file, get_async_task_mock

MOCK_COALESCER = './tests/unit/poller/shared/coalescer_mock.py'


@pytest.fixture
def coalescer_cfg():
    """Generate a random data directory where to start the poller
    """
    cfg_file = create_dummy_config_file()
    yield cfg_file
    os.remove(cfg_file)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.coalescer_launcher
def test_coalescer_launcher_init(coalescer_cfg):
    """Test coalescer initialization
    """
    cfg_file = coalescer_cfg
    cfg = load_sq_config(config_file=cfg_file)
    coalescer_bin = 'coalescer.py'
    cl = CoalescerLauncher(cfg_file, cfg, coalescer_bin)
    # Check if parameters have been correctly initialized
    assert cfg_file == cl.config_file
    assert cfg == cl.cfg
    assert coalescer_bin == cl.coalescer_bin


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.coalescer_launcher
def test_coalescer_launcher_init_default_bin(coalescer_cfg):
    """Test coalescer initialization with default bin argument
    """
    cfg_file = coalescer_cfg
    cfg = load_sq_config(config_file=cfg_file)
    cl = CoalescerLauncher(cfg_file, cfg)
    # Check if parameters have been correctly initialized
    assert cfg_file == cl.config_file
    assert cfg == cl.cfg
    assert cl.coalescer_bin


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.coalescer_launcher
@pytest.mark.asyncio
async def test_coalescer_start(coalescer_cfg):
    """Launch a mock coalescer in order to check if it is possible
    to start it. The mock listen on TCP port 8303 waiting for a
    connection from this test.
    """
    cfg_file = coalescer_cfg
    cfg = load_sq_config(config_file=cfg_file)
    cl = CoalescerLauncher(cfg_file, cfg, MOCK_COALESCER)
    # Start coalescer
    task = asyncio.create_task(cl.start_and_monitor_coalescer())
    # Waiting for coalescer to start
    await asyncio.sleep(1)
    try:
        # Try to reach the coalescer mock
        _, writer = await asyncio.open_connection(
            '127.0.0.1', 8303)
        writer.close()
        await writer.wait_closed()

        # Check if the task is still running
        if task.done():
            raise Exception('The start_and_monitor_coalescer task terminated '
                            'but the coalescer is still running.')
    except ConnectionRefusedError:
        pytest.fail('Unable to connect to the coalescer mock')
    except Exception as e:  # pylint: disable=broad-except
        pytest.fail(str(e))
    finally:
        task.cancel()
        await task


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.coalescer_launcher
@pytest.mark.asyncio
async def test_coalescer_keep_on_failing(coalescer_cfg):
    """Try to start a coalescer which keep on failing
    """
    cfg_file = coalescer_cfg
    cfg = load_sq_config(config_file=cfg_file)
    cl = CoalescerLauncher(cfg_file, cfg, MOCK_COALESCER)

    monitor_process_fn = get_async_task_mock()
    dummy_process = MagicMock()
    dummy_process.returncode = 1
    start_coalescer_fn = get_async_task_mock(dummy_process)

    try:
        with patch.multiple(CoalescerLauncher,
                            _start_coalescer=start_coalescer_fn), \
            patch.multiple(coalescer_launcher_module,
                           monitor_process=monitor_process_fn):
            await asyncio.wait_for(cl.start_and_monitor_coalescer(), 5)
        # Check if multiple attempts have been performed
        attempts_done = start_coalescer_fn.call_count
        assert attempts_done == cl.max_attempts, \
            f'Expected {cl.max_attempts} attempts, {attempts_done} done'
    except asyncio.TimeoutError:
        pytest.fail(
            'The coalescer launcher task expected to file but it does not')


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.coalescer_launcher
@pytest.mark.asyncio
async def test_coalescer_wrong_attempts_number(coalescer_cfg):
    """Test if an exception is raised if a wrong number of attempts is passed
    to the coalescer launcher
    """
    cfg_file = coalescer_cfg
    cfg = load_sq_config(config_file=cfg_file)
    with pytest.raises(PollingError, match=r'The number of attempts*'):
        CoalescerLauncher(cfg_file, cfg, MOCK_COALESCER, max_attempts=0)
