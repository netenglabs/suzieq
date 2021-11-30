"""
This module contains the Poller logic
"""

import asyncio
import logging
import os
import signal
from pathlib import Path

from suzieq.poller.coalescer import start_and_monitor_coalescer
from suzieq.poller.inventory.inventory_sources_base.inventory import Inventory
from suzieq.poller.services import init_services
from suzieq.poller.writers.output_worker_manager import OutputWorkerManager

logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, userargs, cfg):
        self._validate_poller_args(userargs, cfg)

        # Set configuration parameters
        self.userargs = userargs
        self.cfg = cfg

        self.waiting_tasks = []
        self.waiting_tasks_lock = asyncio.Lock()
        self.services = []
        self.running_svcs = []
        # Init the node inventory object
        self.inventory = self._init_inventory()

        # Prepare the services to run
        self.services_list = self._evaluate_service_list()
        self.default_svc_period = self.cfg.get('poller', {}).get('period', 15)
        self.run_mode = self.userargs.run_once or 'forever'

        # Set the service schemas directory
        self.service_dir = cfg['service-directory']
        self.svc_schema_dir = cfg.get('schema-directory', None)
        if not self.svc_schema_dir:
            self.svc_schema_dir = '{}/{}'.format(self.service_dir, 'schema')
        # TODO: check schema dir validity

        # Disable coalescer in specific, unusual cases
        # in case of input_dir, we also seem to leave a coalescer
        # instance running
        if userargs.run_once or userargs.input_dir:
            userargs.no_coalescer = True

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

    async def init_poller(self):
        """Initialize the poller, instantiating the services and setting up
        the connection with the nodes. This function should be called only
        at the beginning before calling run().
        """

        logger.info('Initializing poller')

        init_tasks = []
        init_tasks.append(self.inventory.build_inventory())

        init_tasks.append(init_services(self.service_dir, self.svc_schema_dir,
                          self.output_queue, self.services_list,
                          self.default_svc_period,
                          self.run_mode))

        nodes, self.services = await asyncio.gather(*init_tasks)

        if not nodes or not self.services:
            # Logging should've been done by init_nodes/services for details
            raise AttributeError('Terminating because no nodes'
                                 'or services found')

    async def run(self):
        """Start polling the devices.
        Before running this function the poller should be initialized.
        """

        # Add the node list in the services
        await self.update_node_list()

        logger.info('Suzieq Started')

        # When the poller receives a termination signal, we would like
        # to gracefully terminate all the tasks, i.e. closing all the
        # connections with nodes.
        loop = asyncio.get_event_loop()
        for s in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self._stop(s)))

        # Schedule the tasks to run
        await self.inventory.schedule_nodes_run()
        await self._schedule_services_run()
        await self._add_poller_task([self.output_manager.run_output_workers()])
        if not self.userargs.no_coalescer:
            await self._add_poller_task(
                [start_and_monitor_coalescer(self.userargs.config,
                                             self.cfg,
                                             logger)]
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
                    if tasks and any(i._coro in self.running_svcs
                                     for i in tasks):
                        continue
                    else:
                        break
                except asyncio.CancelledError:
                    break
        finally:
            logger.warning('sq-poller: Received terminate signal. Terminating')
            loop.stop()

    async def update_node_list(self):
        """Update the list of nodes queried by the services according to the
        the nodes in the inventory.
        """
        node_callq = self.inventory.get_node_callq()
        for svc in self.services:
            await svc.set_nodes(node_callq)

    async def _add_poller_task(self, tasks):
        """Add new tasks to be executed in the poller run loop."""

        await self.waiting_tasks_lock.acquire()
        self.waiting_tasks += tasks
        self.waiting_tasks_lock.release()

    async def _schedule_services_run(self):
        # TODO: Add check if services are already running
        self.running_svcs = [svc.run() for svc in self.services]
        await self._add_poller_task(self.running_svcs)

    def _evaluate_service_list(self):
        """Constuct the list of the name of the services to be started
        in the poller, according to the arguments passed by the user.
        Returns a InvalidAttribute exception if any of the passed service
        is invalid.
        """

        svcs = list(Path(self.cfg['service-directory']).glob('*.yml'))
        allsvcs = [os.path.basename(x).split('.')[0] for x in svcs]
        svclist = None

        if self.userargs.service_only:
            svclist = self.userargs.service_only.split()

            # Check if all the given services are valid
            notvalid = [s for s in svclist if s not in allsvcs]
            if notvalid:
                raise AttributeError(f'Invalid sevices specified: {notvalid}. '
                                     f'Should have been one of {allsvcs}')
        else:
            svclist = allsvcs

        if self.userargs.exclude_services:
            excluded_services = self.userargs.exclude_services.split()
            # Check if all the excluded services are valid
            notvalid = [e for e in excluded_services if e not in allsvcs]
            if notvalid:
                raise AttributeError(f'Services {notvalid} excluded, but they '
                                     'are not valid services')
            svclist = list(filter(lambda x: x not in excluded_services,
                                  svclist))

        if not svclist:
            raise AttributeError('The list of services to execute is empty')
        return svclist

    def _init_inventory(self):

        # Define the dictionary with the settings
        # for any kind of inventory source
        connect_timeout = self.cfg.get('poller', {}).get('connect-timeout', 15)
        inventory_args = {
            'passphrase': self.userargs.passphrase,
            'jump_host': self.userargs.jump_host,
            'jump_host_key_file': self.userargs.jump_host_key_file,
            'password': self.userargs.ask_pass,
            'connect_timeout': connect_timeout,
            'ssh_config_file': self.userargs.ssh_config_file,
            'ignore_known_hosts': self.userargs.ignore_known_hosts
        }

        # Retrieve the specific inventory source to use
        inv_types = Inventory.get_plugins(
            "suzieq.poller.inventory.inventory_sources",
            transitive=True
        )
        # TODO: define a generic way to specify the source of the inventory
        inventory_class = None
        source_args = {}

        if self.userargs.input_dir:
            # 'dir' is not a real inventory source
            # we need to override the Inventory class
            # in order to simulate nodes providing the data
            # inside the specified input directory.
            inventory_class = inv_types['dir']
            source_args = {'input_dir': self.userargs.input_dir}
        elif self.userargs.devices_file:
            inventory_class = inv_types['file']
            source_args = {'inventory': self.userargs.devices_file}
        else:
            inventory_class = inv_types['ansible']
            source_args = {
                'ansible_file': self.userargs.ansible_file,
                'default_namespace': self.userargs.namespace
            }

        return inventory_class(self._add_poller_task,
                               **source_args,
                               **inventory_args)

    async def _init_services(self):
        """Instantiate the services to run in the poller"""
        pass

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

    def _validate_poller_args(self, userargs, cfg):
        """Validate the arguments and the configuration passed to the poller.
        The function produces a AttributeError exception if there is something
        wrong in the configuration.
        """
        if userargs.devices_file and userargs.namespace:
            raise AttributeError('Cannot specify both -D and -n options')
        if not os.path.isdir(cfg['service-directory']):
            raise AttributeError(
                f"Service directory {cfg['service-directory']} "
                "is not a directory"
            )
        if userargs.jump_host and not userargs.jump_host.startswith('//'):
            raise AttributeError(
                'Jump host format is //<username>@<jumphost>:<port>'
            )

        if userargs.jump_host_key_file:
            if not userargs.jump_host:
                raise AttributeError(
                    'Jump host key specified without a jump host'
                )
            else:
                if not os.access(userargs.jump_host_key_file, os.F_OK):
                    raise AttributeError(
                        f'Jump host key file {userargs.jump_host_key_file}'
                        'does not exist'
                    )
                if not os.access(userargs.jump_host_key_file, os.R_OK):
                    raise AttributeError(
                        f'Jump host key file {userargs.jump_host_key_file} '
                        'not readable'
                    )

        if userargs.ssh_config_file:
            ssh_config_file = os.path.expanduser(userargs.ssh_config_file)
            if (os.stat(
                    os.path.dirname(
                        ssh_config_file)).st_mode | 0o40700 != 0o40700):
                raise AttributeError(
                    'ssh directory has wrong permissions, must be 0700')
