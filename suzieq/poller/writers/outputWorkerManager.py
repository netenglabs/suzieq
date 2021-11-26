import asyncio
import logging
from inspect import getfile
from os.path import dirname

from suzieq.poller.writers.outputWorker import OutputWorker
from suzieq.utils import get_subclasses

logger = logging.getLogger(__name__)


class OutputWorkerManager:
    def __init__(self, output_types, output_args) -> None:
        self._output_queue = asyncio.Queue()
        self._output_workers = []

        self._output_types = output_types
        self._output_args = output_args
        self.init_output_workers()

    @property
    def output_queue(self):
        return self._output_queue

    @property
    def output_types(self):
        return self._output_types

    @property
    def output_args(self):
        return self._output_args

    async def run_output_workers(self):
        """Start writing the output data"""
        while True:
            try:
                data = await self._output_queue.get()
            except asyncio.CancelledError:
                logger.error("Writer thread received task cancel")
                return

            if not self._output_workers:
                return

            for worker in self._output_workers:
                worker.write_data(data)

    def init_output_workers(self):
        """Create the appropriate output workers objects and return them"""
        # Load the available output workers
        worker_types = get_subclasses(
            OutputWorker, dirname(getfile(OutputWorker)))
        for otype in self.output_types:
            if otype not in worker_types:
                raise AttributeError(f'{otype} is not a valid output format '
                                     f'pick some of {worker_types.keys()}')
            new_worker = worker_types[otype](**self.output_args)
            self._output_workers.append(new_worker)
