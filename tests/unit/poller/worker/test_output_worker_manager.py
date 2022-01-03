"""
Test the OutputWorkerManager component
"""
# pylint: disable=protected-access

import asyncio
from unittest.mock import patch

import pytest
from suzieq.poller.worker.writers.gather import GatherOutputWorker
from suzieq.poller.worker.writers.output_worker_manager import OutputWorkerManager
from suzieq.poller.worker.writers.parquet import ParquetOutputWorker
from suzieq.shared.exceptions import SqPollerConfError
from tests.conftest import _get_async_task_mock

OUTPUT_TYPES = ['parquet', 'gather']
OUTPUT_ARGS = {
    'output_dir': 'tests/unit/poller/worker/poller_output',
    'data_dir': 'tests/unit/poller/worker/poller_output/parquet_out'
}


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker_manager
def test_output_worker_manager_init():
    """Check correct initialization of the OuputWorkerManager
    """
    mgr = OutputWorkerManager(OUTPUT_TYPES, OUTPUT_ARGS)
    # Check if the fields have been correctly assigned
    assert mgr.output_args == OUTPUT_ARGS
    assert mgr.output_types == OUTPUT_TYPES
    assert len(mgr._output_workers) == len(mgr.output_types)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker_manager
def test_wrong_output_worker():
    """Pass not existing OuputWorker
    """
    with pytest.raises(SqPollerConfError):
        OutputWorkerManager(['invalid'], {})


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker_manager
@pytest.mark.asyncio
async def test_run_output_workers(data_to_write):
    """Check if the OutputWorkers are correctly launched
    """
    parquet_write = _get_async_task_mock()
    gather_write = _get_async_task_mock()
    with patch.object(ParquetOutputWorker, 'write_data', parquet_write), \
         patch.object(GatherOutputWorker, 'write_data', gather_write):
        mgr = OutputWorkerManager(OUTPUT_TYPES, OUTPUT_ARGS)
        run_task = asyncio.create_task(mgr.run_output_workers())
        await mgr.output_queue.put(data_to_write)
        # Wait to make the OutputWorkerManager consume the messages
        await asyncio.sleep(0.5)
        # Check if the writers have been called
        parquet_write.assert_called()
        gather_write.assert_called()
        # Stop the OuputWorkerManager
        run_task.cancel()
