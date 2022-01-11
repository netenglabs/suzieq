"""
This module contains the logic for instantiaing
and running the OutputWorkers
"""

import asyncio
import logging
from typing import Dict, List

from suzieq.poller.worker.writers.output_worker import OutputWorker
from suzieq.shared.exceptions import SqPollerConfError

logger = logging.getLogger(__name__)


class OutputWorkerManager:
    """OuputWorkerManager is the class in charge of
    taking care of the OutputWorker instantiation and
    that the polling output is persistened by all the
    OutputWorkers.
    """

    def __init__(self,
                 output_types: List[str],
                 output_args: Dict[str, str]) -> None:
        self._output_queue = asyncio.Queue()
        self._output_workers = []

        self._output_types = output_types
        self._output_args = output_args
        self._init_output_workers()

    @property
    def output_queue(self):
        '''Queue between the poller and the writer'''
        return self._output_queue

    @property
    def output_types(self):
        '''Supported output formats'''
        return self._output_types

    @property
    def output_args(self):
        '''Args supplied on init'''
        return self._output_args

    async def run_output_workers(self):
        """Start writing the output data, watching
        the content of the ouput queue and triggering
        a write on all the configured Ouput
        """
        while True:
            try:
                data = await self._output_queue.get()
            except asyncio.CancelledError:
                logger.warning(
                    'OutputWorkerManager: received signal to terminate'
                )
                return

            if not self._output_workers:
                return

            for worker in self._output_workers:
                worker.write_data(data)

    def _init_output_workers(self):
        """Create the appropriate output workers for persisting the
        poller output.
        """
        # Load the available output workers
        worker_types = OutputWorker.get_plugins()
        for otype in self.output_types:
            if otype not in worker_types:
                raise SqPollerConfError(f'{otype} is not a valid output '
                                        f'pick some of {worker_types.keys()}')
            new_worker = worker_types[otype](**self.output_args)
            self._output_workers.append(new_worker)
