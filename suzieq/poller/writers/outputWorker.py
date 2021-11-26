import abc
import logging
import os

import pyarrow.parquet as pq


class OutputWorker(object):

    def __init__(self, **kwargs):
        self.type = kwargs.get("type", None)
        self.logger = logging.getLogger(__name__)

        output_dir = kwargs.get("output_dir", None)
        if output_dir:
            self.root_output_dir = output_dir
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir)
        else:
            # TBD: The right error to raise here since this is a required
            # keyword
            self.logger.error("Need mandatory keyword arg: output_dir")
            raise ValueError

    @abc.abstractmethod
    def write_data(self, data):
        raise NotImplementedError





