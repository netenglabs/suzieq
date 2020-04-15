import os
import logging

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


class OutputWorker(object):
    type = None

    def __init__(self, **kwargs):
        self.type = kwargs.get("type", None)
        self.logger = logging.getLogger(__name__)

    def write_data(self, data):
        raise NotImplementedError


class ParquetOutputWorker(OutputWorker):

    root_output_dir = None

    def __init__(self, **kwargs):

        super(ParquetOutputWorker, self).__init__(type="parquet")
        output_dir = kwargs.get("output_dir", None)
        if output_dir:
            self.root_output_dir = output_dir
        else:
            # TBD: The right error to raise here since this is a required
            # keyword
            self.logger.error("Need mandatory keyword arg: output_dir")
            raise ValueError

    def write_data(self, data):
        cdir = "{}/{}/".format(self.root_output_dir, data["topic"])
        if not os.path.isdir(cdir):
            os.makedirs(cdir)

        df = pd.DataFrame.from_dict(data["records"])
        # pq.write_metadata(
        #     self.schema,'{}/_metadata'.format(cdir),
        #     version='2.0',
        #     coerce_timestamps='us')

        table = pa.Table.from_pandas(df, schema=data["schema"],
                                     preserve_index=False)

        pq.write_to_dataset(
            table,
            root_path=cdir,
            partition_cols=data["partition_cols"],
            version="2.0",
            flavor="spark",
        )


async def run_output_worker(queue, output_workers):

    while True:
        data = await queue.get()

        for worker in output_workers:
            worker.write_data(data)


def init_output_workers(output_types, output_args):
    """Create the appropriate output worker objects and return them"""

    workers = []
    for otype in output_types:
        if otype == "parquet":
            worker = ParquetOutputWorker(output_dir=output_args["output_dir"])
            if worker:
                workers.append(worker)
        else:
            raise NotImplementedError("Unknown type: {}".format(otype))

    return workers
