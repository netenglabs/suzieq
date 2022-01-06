"""
Test the GatherOutputWorker
"""
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import os
import random
import shutil

import pytest
from suzieq.poller.worker.writers.gather import GatherOutputWorker
from suzieq.shared.exceptions import SqPollerConfError

WRITER_OUTPUT_DIR = 'tests/unit/poller/worker/writers/poller_output/gather'


@pytest.fixture
def gather_output_worker():
    """Init an instance of the ParquetOuputWorker
    """
    # Append random number in order to allow parallel execution of the tests
    random_dir = f'{WRITER_OUTPUT_DIR}_{random.random()}'
    yield GatherOutputWorker(output_dir=random_dir)
    shutil.rmtree(random_dir)


@pytest.fixture
def create_gather_dir():
    """Generate the Parquet output dir
    """
    os.makedirs(WRITER_OUTPUT_DIR)
    yield
    shutil.rmtree(WRITER_OUTPUT_DIR)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker
def test_parquet_writer_init_existing_dir(create_gather_dir):
    """Check the correct initialization of the GatherOutputWorker
    with existing directory
    """
    worker = GatherOutputWorker(output_dir=WRITER_OUTPUT_DIR)
    # Check if the output dir is correct
    assert worker.root_output_dir == WRITER_OUTPUT_DIR
    assert os.path.isdir(WRITER_OUTPUT_DIR)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker
def test_parquet_writer_init(gather_output_worker):
    """Check the correct initialization of the GatherOutputWorker
    with not existing dir
    """
    assert os.path.isdir(gather_output_worker.root_output_dir)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker
def test_wrong_file_instead_directory():
    """Pass a file instead of a data directory
    """
    with pytest.raises(SqPollerConfError):
        GatherOutputWorker(
            output_dir='tests/unit/poller/worker/writers/test_gather.py'
        )


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker
def test_wrong_missing_output_dir():
    """Do not pass an output directory
    """
    with pytest.raises(SqPollerConfError):
        GatherOutputWorker()


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.output_worker
def test_gather_write(gather_output_worker, data_to_write):
    """Write data in the parquet output directory
    """
    data_to_write['records'] = str(data_to_write['records'])
    gather_output_worker.write_data(data_to_write)
    # Check if the file has been created
    out_file = (f'{gather_output_worker.root_output_dir}/'
                f"{data_to_write['topic']}.output")
    assert os.path.isfile(out_file)

    # Check the file content
    with open(out_file, 'r') as f:
        result = f.read()
        assert result == data_to_write['records']
