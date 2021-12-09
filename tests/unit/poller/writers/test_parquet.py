"""
Test the ParquetOutputWorker
"""
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import os
import random
import shutil

import pandas as pd
import pytest
from suzieq.poller.worker.writers.parquet import ParquetOutputWorker
from suzieq.shared.exceptions import SqPollerConfError
from tests.integration.utils import assert_df_equal

WRITER_OUTPUT_DIR = 'tests/unit/poller/writers/poller_output/parquet_out'


@pytest.fixture
def parquet_output_worker():
    """Initializa an instance of the ParquetOuputWorker
    """
    # Append random number in order to allow parallel execution of the tests
    random_dir = f'{WRITER_OUTPUT_DIR}_{random.random()}'
    yield ParquetOutputWorker(data_dir=random_dir)
    shutil.rmtree(random_dir)


@pytest.fixture
def create_parquet_dir():
    """Generate the Parquet output dir
    """
    os.makedirs(WRITER_OUTPUT_DIR)
    yield
    shutil.rmtree(WRITER_OUTPUT_DIR)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.output_worker
def test_parquet_writer_init_existing_dir(create_parquet_dir):
    """Check the correct initialization of the ParquetOutputWorker
    with existing directory
    """
    worker = ParquetOutputWorker(data_dir=WRITER_OUTPUT_DIR)
    # Check if the output dir is correct
    assert worker.root_output_dir == WRITER_OUTPUT_DIR
    assert os.path.isdir(WRITER_OUTPUT_DIR)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.output_worker
def test_parquet_writer_init(parquet_output_worker):
    """Check the correct initialization of the ParquetOutputWorker
    with not existing dir
    """
    assert os.path.isdir(parquet_output_worker.root_output_dir)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.output_worker
def test_wrong_file_instead_directory():
    """Pass a file instead of a data directory
    """
    with pytest.raises(SqPollerConfError):
        ParquetOutputWorker(
            data_dir='tests/unit/poller/writers/test_parquet.py'
        )


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.output_worker
def test_parquet_write(parquet_output_worker, data_to_write):
    """Write data in the parquet output directory
    """
    parquet_output_worker.write_data(data_to_write)
    parquet_dir = (f'{parquet_output_worker.root_output_dir}/'
                   f"{data_to_write['topic']}")
    assert os.path.isdir(parquet_dir)
    # Build directory location
    file_location = ""
    for prt in data_to_write['partition_cols']:
        file_location += f"/{prt}={data_to_write['records'][0][prt]}"

    # Search for the written file
    search_location = f'{parquet_dir}{file_location}'
    for file in os.listdir(search_location):
        # Read back the data and compare it with what is expected
        expected_df = pd.DataFrame.from_dict(data_to_write["records"])
        written_df = pd.read_parquet(f'{search_location}/{file}')
        # Sort dfs indexes
        expected_df = expected_df.reindex(sorted(expected_df.columns), axis=1)
        written_df = written_df.reindex(sorted(written_df.columns), axis=1)
        assert_df_equal(expected_df, written_df,
                        data_to_write['partition_cols'])
