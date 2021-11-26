import asyncio
import logging
import os
import signal
from collections import defaultdict
from pathlib import Path

from suzieq.poller.coalescer import start_and_monitor_coalescer
from suzieq.poller.nodes import init_files, init_hosts
from suzieq.poller.services import init_services

logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, userargs, cfg):
        self._validate_poller_args(userargs, cfg)

        self.services = []
        self.nodes = []
        self.waiting_tasks = []
        self.waiting_tasks_lock = asyncio.Lock()

        # Set configuration parameters
        self.userargs = userargs
        self.cfg = cfg

        # Set the service schemas directory
        self.schema_dir = cfg.get('schema-directory', None)
        if not self.schema_dir:
            self.schema_dir = '{}/{}'.format(userargs.service_dir, 'schema')

        # Disable coalescer in specific, unusual cases
        # in case of input_dir, we also seem to leave a coalescer 
        # instance running
        if userargs.run_once or userargs.input_dir:
            userargs.no_coalescer = True

        # Setup poller writers
        self.output_args = {}
        self.output_queue = asyncio.Queue()
        self.output_workers = []

        # TODO: move to the Parquet writer class        
        if 'parquet' in userargs.outputs:
            validate_parquet_args(cfg, self.output_args, logger)

        if userargs.run_once:
            userargs.outputs = ['gather']
            self.output_args['output_dir'] = userargs.output_dir

        self.output_workers = init_output_workers(userargs.outputs, self.output_args)

        # Prepare the list of services to run
        self.services_list = self._evaluate_service_list()

    async def init_poller(self):
        """Initialize the poller, instantiating the services and setting up
        the connection with the nodes. This function should be called only
        at the beginning before calling run().
        """

        logger.info('Initializing poller')

        connect_timeout = self.cfg.get('poller', {}).get('connect-timeout', 15)
        
        tasks = []
        if self.userargs.input_dir:
            tasks.append(init_files(self.userargs.input_dir))
        else:
            tasks.append(init_hosts(inventory=self.userargs.devices_file,
                                    ans_inventory=self.userargs.ansible_file,
                                    namespace=self.userargs.namespace,
                                    passphrase=self.userargs.passphrase,
                                    jump_host=self.userargs.jump_host,
                                    jump_host_key_file=self.userargs.jump_host_key_file,
                                    password=self.userargs.ask_pass,
                                    connect_timeout=connect_timeout,
                                    ssh_config_file=self.userargs.ssh_config_file,
                                    ignore_known_hosts=self.userargs.ignore_known_hosts))

        period = self.cfg.get('poller', {}).get('period', 15)

        tasks.append(init_services(self.cfg['service-directory'], self.schema_dir, 
                     self.output_queue, self.services_list, period, 
                     self.userargs.run_once or 'forever'))

        self.nodes, self.services = await asyncio.gather(*tasks)

        if not self.nodes or not self.services:
            # Logging should've been done by init_nodes/services for details
            raise AttributeError('Terminating because no nodes'
                                 'or services found')

    async def run(self):
        """Start polling the devices. 
        Before running this function the poller should be initialized.
        """

        node_callq = defaultdict(lambda: defaultdict(dict))

        node_callq.update({x: {'hostname': self.nodes[x].hostname,
                               'postq':    self.nodes[x].post_commands}
                           for x in self.nodes})

        for svc in self.services:
            svc.set_nodes(node_callq)

        logger.info('Suzieq Started')

        loop = asyncio.get_event_loop()
        for s in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self._stop(s)))

        try:
            # The logic below of handling the writer worker task separately 
            # is to ensure we can terminate properly when all the other 
            # tasks have finished as in the case of using file input 
            # instead of SSH
            svc_tasks = [svc.run() for svc in self.services]
            tasks = [self.nodes[node].run() for node in self.nodes]
            tasks += [run_output_worker(self.output_queue, self.output_workers, logger)]
            tasks += svc_tasks

            if not self.userargs.no_coalescer:
                tasks += [start_and_monitor_coalescer(self.userargs.config, self.cfg,
                                                      logger)]
            while tasks:
                try:
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED)
                    tasks = list(pending)
                    if tasks and any(i._coro in svc_tasks for i in tasks):
                        continue
                    else:
                        break
                except asyncio.CancelledError:
                    break
        finally:
            logger.warning('sq-poller: Received terminate signal. Terminating')
            loop.stop()
            return

    async def _init_services():
        """Instantiate the services to run in the poller"""
        pass

    async def _add_poller_task(self, task):
        """Add a new task to be executed in the poller run loop."""

        await self.waiting_tasks_lock.acquire()
        self.waiting_tasks.append(task)
        self.waiting_tasks_lock.release()

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
        if not os.path.exists(cfg['service-directory']):
            raise AttributeError('Service directory {} is not a directory'.format(
                cfg['service-directory'])
            )

        if userargs.jump_host and not userargs.jump_host.startswith('//'):
            raise AttributeError(
                'Jump host format is //<username>@<jumphost>:<port>')

        if userargs.jump_host_key_file:
            if not userargs.jump_host:
                raise AttributeError(
                    'Jump host format is //<username>@<jumphost>:<port>')
            else:
                if not os.access(userargs.jump_host_key_file, os.F_OK):
                    raise AttributeError(
                        f'Jump host key file {userargs.jump_host_key_file} does not exist')
                if not os.access(userargs.jump_host_key_file, os.R_OK):
                    raise AttributeError(
                        f'Jump host key file {userargs.jump_host_key_file} not readable')

        if userargs.ssh_config_file:
            ssh_config_file = os.path.expanduser(userargs.ssh_config_file)
            if (os.stat(
                    os.path.dirname(
                        ssh_config_file)).st_mode | 0o40700 != 0o40700):
                raise AttributeError(
                    'ssh directory has wrong permissions, must be 0700')
