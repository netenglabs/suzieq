"""
This module contains the Poller logic
"""

import argparse
import asyncio
import logging
import os
import signal
from typing import Dict, Type

from suzieq.poller.worker.inventory.inventory import Inventory
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.poller.worker.writers.output_worker_manager \
    import OutputWorkerManager
from suzieq.shared.exceptions import SqPollerConfError

logger = logging.getLogger(__name__)


class Worker:
    """Worker is the object in charge of coordinating services, nodes and
    output worker tasks, in order to pull the data from the devices configured
    in the device inventory.
    """

    DEFAULT_INVENTORY = 'static'

    def __init__(self, userargs, cfg):
        self._validate_worker_args(userargs, cfg)

        # Set the worker id
        self.worker_id = userargs.worker_id

        # Setup poller tasks list
        self.waiting_tasks = []
        self.waiting_tasks_lock = asyncio.Lock()

        # Setup poller writers

        # TODO: At the moment:
        # output_dir: is the directory used by the gather method
        # data_dir: is the directory used by parquet
        # we need a way to define the settings
        # for each type of output worker
        self.output_args = {
            'output_dir': userargs.output_dir,
            'data_dir': cfg.get('data-directory')
        }

        if userargs.run_once in ['gather', 'process']:
            userargs.outputs = ['gather']
        self.output_manager = OutputWorkerManager(userargs.outputs,
                                                  self.output_args)
        self.output_queue = self.output_manager.output_queue

        # Initialize service manager
        service_dir = cfg['service-directory']
        svc_schema_dir = cfg.get('schema-directory', None)
        default_svc_period = cfg.get('poller', {}).get('period', 15)
        run_mode = userargs.run_once or 'forever'
        svc_manager_args = {
            'service_only': userargs.service_only,
            'exclude_services': userargs.exclude_services,
            'outputs': userargs.outputs
        }
        self.service_manager = ServiceManager(self._add_worker_tasks,
                                              service_dir,
                                              svc_schema_dir,
                                              self.output_queue,
                                              run_mode,
                                              cfg,
                                              default_svc_period,
                                              **svc_manager_args)

        # Init the node inventory object
        self.inventory = self._init_inventory(userargs, cfg)

    async def init_worker(self):
        """Initialize the worker, instantiating the services and setting up
        the connection with the nodes. This function should be called only
        at the beginning before calling run().
        """

        logger.info('Initializing poller worker')

        # When the poller receives a termination signal, we would like
        # to gracefully terminate all the tasks, i.e. closing all the
        # connections with nodes.
        loop = asyncio.get_event_loop()
        for s in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self._stop()))

        init_tasks = []
        init_tasks.append(self.inventory.build_inventory())
        init_tasks.append(self.service_manager.init_services())

        nodes, services = await asyncio.gather(*init_tasks)

        if not nodes:
            # Get the logger filename
            root_logger = logging.getLogger()
            log_filename = ""
            for h in root_logger.handlers:
                if hasattr(h, 'baseFilename'):
                    log_filename = h.baseFilename
                    break

            raise SqPollerConfError(
                f'No nodes could be polled. Check {log_filename} for errors '
                'in connecting'
            )
        if not services:
            raise SqPollerConfError('No services candidate for execution')

    async def run(self):
        """Start polling the devices.
        Before running this function the worker should be initialized.
        """

        # Add the node list in the services
        await self.service_manager.set_nodes(self.inventory.get_node_callq())

        logger.info('Suzieq Started')

        # Schedule the tasks to run
        await self.inventory.schedule_nodes_run()
        await self.service_manager.schedule_services_run()
        await self._add_worker_tasks(
            [self.output_manager.run_output_workers()])

        try:
            # The logic below of handling the writer worker task separately
            # is to ensure we can terminate properly when all the other
            # tasks have finished as in the case of using file input
            # instead of SSH
            tasks = await self._pop_waiting_worker_tasks()
            while tasks:
                try:
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED)
                    for d in done:
                        if d.exception():
                            raise d.exception()
                    tasks = list(pending)
                    running_svcs = self.service_manager.running_services
                    if tasks and any(i._coro in running_svcs
                                     for i in tasks):
                        continue

                    break
                except asyncio.CancelledError:
                    break
        except asyncio.CancelledError:
            logger.warning('Received terminate signal. Terminating...')

    async def _add_worker_tasks(self, tasks):
        """Add new tasks to be executed in the poller worker run loop."""

        await self.waiting_tasks_lock.acquire()
        self.waiting_tasks += tasks
        self.waiting_tasks_lock.release()

    def _get_inventory_plugins(self) -> Dict[str, Type]:
        """Get all types of inventory it is possible to instantiate

        Returns:
            Dict[str, Type]: a dictionary containing the name of the inventory
                type and its class
        """
        return Inventory.get_plugins()

    def _init_inventory(self, userargs: argparse.Namespace, cfg: Dict,
                        addnl_args: Dict = None):
        """Initialize the Inventory object, in charge of retrieving the
        list of nodes this worker is in charge to poll

        Args:
            userargs (argparse.Namespace): the cli arguments
            cfg (Dict): the content of the SuzieQ config file
            addnl_args (Dict): additional arguments to pass to the init
                function of the Inventory class

        Raises:
            SqPollerConfError: raised if a wrong configuration is provided
        """

        # Define the dictionary with the settings
        # for any kind of inventory source
        connect_timeout = cfg.get('poller', {}).get('connect-timeout', 15)
        inventory_args = {
            'connect_timeout': connect_timeout,
            'ssh_config_file': userargs.ssh_config_file,
        }

        if addnl_args:
            inventory_args.update(addnl_args)

        # Retrieve the specific inventory source to use
        inv_types = self._get_inventory_plugins()

        inventory_class = None
        source_args = {}

        if userargs.input_dir:
            # 'dir' is not a real inventory source
            # we need to override the Inventory class
            # in order to simulate nodes providing the data
            # inside the specified input directory.
            inventory_class = inv_types['dir']
            source_args = {'input_dir': userargs.input_dir}
        else:
            mgr_cfg = cfg.get('poller', {}).get('manager', {})
            type_to_use = mgr_cfg.get('type', self.DEFAULT_INVENTORY)
            inventory_class = inv_types.get(type_to_use)
            if not inventory_class:
                raise SqPollerConfError(f'No inventory {type_to_use} found')
            source_args = {
                **mgr_cfg,
                'worker-id': self.worker_id
            }

        return inventory_class(self._add_worker_tasks,
                               **source_args,
                               **inventory_args)

    async def _pop_waiting_worker_tasks(self):
        """Empty the list of tasks to be added in the run loop
        and return its content.
        """

        # Since the function is asynchronous and we need to
        # read the content of the task list and, at the end, empty
        # it, we need to handle concurrency. Otherwise we risk to loose
        # all the tasks added after the list has been read, but before
        # the list emptying.
        await self.waiting_tasks_lock.acquire()
        poller_tasks = self.waiting_tasks
        self.waiting_tasks = []
        self.waiting_tasks_lock.release()

        return poller_tasks

    async def _stop(self):
        """Stop the worker"""

        tasks = [t for t in asyncio.all_tasks()
                 if t is not asyncio.current_task()]

        for task in tasks:
            task.cancel()

    def _validate_worker_args(self, userargs: Dict, _):
        """Validate the arguments and the configuration passed to the poller.
        The function produces a SqPollerConfError exception if there is
        something wrong in the configuration.

        Args:
            userargs (Dict): Dictionary containing the arguments passed to the
                poller
            cfg (Dict): The content of the Suzieq configuration file

        Raises:
            SqPollerConfError: raise when the configuration is not valid
        """

        if userargs.ssh_config_file:
            if not os.access(userargs.ssh_config_file, os.F_OK):
                raise SqPollerConfError(
                    f'Unable to read ssh config in {userargs.ssh_config_file}'
                )
            ssh_config_file = os.path.expanduser(userargs.ssh_config_file)
            if (os.stat(
                    os.path.dirname(
                        ssh_config_file)).st_mode | 0o40700 != 0o40700):
                raise SqPollerConfError(
                    'ssh directory has wrong permissions, must be 0700'
                )
