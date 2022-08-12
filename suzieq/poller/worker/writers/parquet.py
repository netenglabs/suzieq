"""
This module contains the logic of the writer for the 'parquet' mode
"""
import logging
import os
from typing import Dict

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from suzieq.db.parquet.parquetdb import PARQUET_VERSION
from suzieq.poller.worker.writers.output_worker import OutputWorker
from suzieq.shared.exceptions import SqPollerConfError

logger = logging.getLogger(__name__)


class ParquetOutputWorker(OutputWorker):
    """ParquetOutputWorker writes the data retrived by
    the poller in a parquet output directory
    """

    def __init__(self, **kwargs):
        data_directory = kwargs.get('data_dir')

        if not data_directory:
            output_dir = '/tmp/suzieq/parquet-out/'
            logger.warning(
                'No output directory for parquet specified, using '
                '/tmp/suzieq/parquet-out'
            )
        else:
            output_dir = data_directory

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if not os.path.isdir(output_dir):
            raise SqPollerConfError(
                f'Output directory {output_dir} is not a directory'
            )

        logger.info(f'Parquet outputs will be under {output_dir}')
        self.root_output_dir = output_dir

    def write_data(self, data: Dict):
        """Write the data into the Parquet output directory

        Args:
            data (Dict): dictionary containing the data to store.
        """
        cdir = os.path.join(self.root_output_dir, data['topic'])
        if not os.path.isdir(cdir):
            os.makedirs(cdir)

        # dtypes = {x: data['schema'].field(x).type.__str__()
        #           if 'list' not in data['schema'].field(x).type.__str__()
        #           else data['schema'].field(x).type.to_pandas_dtype()
        #           for x in data['schema'].names}

        df = pd.DataFrame.from_dict(data['records'])
        # df.to_parquet(
        #     path=cdir,
        #     partition_cols=data['partition_cols'],
        #     index=True,
        #     engine='pyarrow')
        # pq.write_metadata(
        #     self.schema,'{}/_metadata'.format(cdir),
        #     version='2.0',
        #     coerce_timestamps='us')

        table = pa.Table.from_pandas(df, schema=data['schema'],
                                     preserve_index=False)

        pq.write_to_dataset(
            table,
            root_path=cdir,
            partition_cols=data['partition_cols'],
            version=PARQUET_VERSION,
            compression='ZSTD',
            row_group_size=100000,
        )
