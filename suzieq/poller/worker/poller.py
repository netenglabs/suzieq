"""
This module contains the Poller logic
"""

import asyncio
import logging
import os
import signal
from typing import Dict

from suzieq.poller.worker.coalescer_launcher import CoalescerLauncher
from suzieq.poller.worker.inventory.inventory import Inventory
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.poller.worker.writers.output_worker_manager \
     import OutputWorkerManager
from suzieq.shared.exceptions import SqPollerConfError

logger = logging.getLogger(__name__)


class Poller:
    """Poller is the object in charge of coordinating services, nodes and
    output worker tasks, in order to pull the data from the devices configured
    in the device inventory.
    """

    def __init__(self, userargs, cfg):
        self._validate_poller_args(userargs, cfg)

        # Set the worker id
        self.worker_id = userargs.worker_id

        # Setup poller tasks list
        self.waiting_tasks = []
        self.waiting_tasks_lock = asyncio.Lock()

        # Init the node inventory object
        self.inventory = self._init_inventory(userargs, cfg)

        # Disable coalescer in specific, unusual cases
        # in case of input_dir, we also seem to leave a coalescer
        # instance running
        self.no_coalescer = userargs.no_coalescer
        if userargs.run_once or userargs.input_dir:
            self.no_coalescer = True
        else:
            self.coalescer_launcher = CoalescerLauncher(userargs.config, cfg)

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

        if userargs.run_once:
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
            'exclude_services': userargs.exclude_services
        }
        self.service_manager = ServiceManager(self._add_poller_task,
                                              service_dir,
                                              svc_schema_dir,
                                              self.output_queue,
                                              run_mode,
                                              default_svc_period,
                                              **svc_manager_args)

    async def init_poller(self):
        """Initialize the poller, instantiating the services and setting up
        the connection with the nodes. This function should be called only
        at the beginning before calling run().
        """

        logger.info('Initializing poller')

        init_tasks = []
        init_tasks.append(self.inventory.build_inventory())
        init_tasks.append(self.service_manager.init_services())

        nodes, services = await asyncio.gather(*init_tasks)

        if not nodes or not services:
            # Logging should've been done by init_nodes/services for details
            raise SqPollerConfError('Terminating because no nodes'
                                    'or services found')

    async def run(self):
        """Start polling the devices.
        Before running this function the poller should be initialized.
        """

        # Add the node list in the services
        await self.service_manager.set_nodes(self.inventory.get_node_callq())

        logger.info('Suzieq Started')

        # When the poller receives a termination signal, we would like
        # to gracefully terminate all the tasks, i.e. closing all the
        # connections with nodes.
        loop = asyncio.get_event_loop()
        for s in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self._stop()))

        # Schedule the tasks to run
        await self.inventory.schedule_nodes_run()
        await self.service_manager.schedule_services_run()
        await self._add_poller_task([self.output_manager.run_output_workers()])
        # Schedule the coalescer if needed
        if not self.no_coalescer:
            await self._add_poller_task(
                [self.coalescer_launcher.start_and_monitor_coalescer()]
            )

        try:
            # The logic below of handling the writer worker task separately
            # is to ensure we can terminate properly when all the other
            # tasks have finished as in the case of using file input
            # instead of SSH
            tasks = await self._pop_waiting_poller_tasks()
            while tasks:
                try:
                    _, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED)
                    tasks = list(pending)
                    running_svcs = self.service_manager.running_services
                    # pylint: disable=protected-access
                    if tasks and any(i._coro in running_svcs
                                     for i in tasks):
                        continue

                    break
                except asyncio.CancelledError:
                    break
        finally:
            logger.warning('sq-poller: Received terminate signal. Terminating')
            loop.stop()

    async def _add_poller_task(self, tasks):
        """Add new tasks to be executed in the poller run loop."""

        await self.waiting_tasks_lock.acquire()
        self.waiting_tasks += tasks
        self.waiting_tasks_lock.release()

    def _init_inventory(self, userargs, cfg):

        # Define the dictionary with the settings
        # for any kind of inventory source
        connect_timeout = cfg.get('poller', {}).get('connect-timeout', 15)
        inventory_args = {
            'connect_timeout': connect_timeout,
            'ssh_config_file': userargs.ssh_config_file,
        }

        # Retrieve the specific inventory source to use
        inv_types = Inventory.get_plugins()
        # TODO: define a generic way to specify the source of the inventory
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
            type_to_use = mgr_cfg.get('type', 'static_manager')
            inventory_class = inv_types[type_to_use]
            source_args = {
                           **mgr_cfg,
                           'worker-id': self.worker_id
                          }

        return inventory_class(self._add_poller_task,
                               **source_args,
                               **inventory_args)

    async def _pop_waiting_poller_tasks(self):
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
        """Stop the poller"""

        tasks = [t for t in asyncio.all_tasks()
                 if t is not asyncio.current_task()]

        for task in tasks:
            task.cancel()

    def _validate_poller_args(self, userargs: Dict, _):
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

        if userargs.jump_host and not userargs.jump_host.startswith('//'):
            raise SqPollerConfError(
                'Jump host format is //<username>@<jumphost>:<port>'
            )

        if userargs.jump_host_key_file:
            if not userargs.jump_host:
                raise SqPollerConfError(
                    'Jump host key specified without a jump host'
                )

            if not os.access(userargs.jump_host_key_file, os.F_OK):
                raise SqPollerConfError(
                    f'Jump host key file {userargs.jump_host_key_file}'
                    'does not exist'
                )
            if not os.access(userargs.jump_host_key_file, os.R_OK):
                raise SqPollerConfError(
                    f'Jump host key file {userargs.jump_host_key_file} '
                    'not readable'
                )

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
