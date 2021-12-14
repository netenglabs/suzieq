"""
This module contains all the common logic
of the Suzieq poller output workers
"""
import abc
import logging
import os
from typing import Dict
from suzieq.shared.exceptions import SqPollerConfError

from suzieq.shared.sq_plugin import SqPlugin


class OutputWorker(SqPlugin):
    """OutputWorker is the base class for all the objects
    implementing the logic to persist the output of the polling
    """
    def __init__(self, **kwargs):
        self.type = kwargs.get('type', None)
        self.logger = logging.getLogger(__name__)

        output_dir = kwargs.get('output_dir', None)
        if output_dir:
            self.root_output_dir = output_dir
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            elif not os.path.isdir(output_dir):
                raise SqPollerConfError(f'Output directory {output_dir}'
                                        'is not a directory')
        else:
            raise SqPollerConfError('Need mandatory keyword arg: output_dir')

    @abc.abstractmethod
    def write_data(self, data: Dict):
        """Write the data into the ouput source"

        Args:
            data (Dict): dictionary containing the data to store.
        """
        raise NotImplementedError
