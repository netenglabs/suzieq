"""
Test the CoalescerLauncher component
"""
# pylint: disable=redefined-outer-name

import asyncio
import os
import signal
from contextlib import suppress

import pytest
from suzieq.poller.worker.coalescer_launcher import CoalescerLauncher
from suzieq.shared.utils import ensure_single_instance, load_sq_config
from tests.conftest import create_dummy_config_file

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
    await asyncio.sleep(11)
    try:
        # Try to reach the coalescer mock
        _, writer = await asyncio.open_connection(
            '127.0.0.1', 8303)
        writer.close()
        await writer.wait_closed()
        # Check if it is possible to get the file lock, if the coalescer
        # is properly running, we should not be able to acquire the lock
        coalesce_dir = cfg.get('coalescer', {})\
            .get('coalesce-directory',
                 f'{cfg.get("data-directory")}/coalesced')
        assert ensure_single_instance(
            f'{coalesce_dir}/.sq-coalescer.pid', False) == 0

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
        coalescer_pid = cl.coalescer_pid
        if coalescer_pid:
            with suppress(OSError):
                os.kill(cl.coalescer_pid, signal.SIGKILL)
