"""This module manages and coordinates all the plugins

Classes:
    InventoryProvider: manages all the plugins

Functions:
    sq_main(): this function coordinates all the plugins initializing
                and starting each one of them. The plugins are divided
                in types.
"""
import argparse
import asyncio
import logging
import signal
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Type

from suzieq.poller.controller.base_controller_plugin import ControllerPlugin
from suzieq.poller.controller.inventory_async_plugin import \
    InventoryAsyncPlugin
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import sq_get_config_file

logger = logging.getLogger(__name__)


class Controller:
    """This class manages all the plugins set on the configuration files
    """

    def __init__(self, args: argparse.Namespace, config_data: dict) -> None:
        # contains the Plugin objects divided by type
        self._plugin_objects = {}

        # collect basePlugin classes
        base_plugin_pkg = 'suzieq.poller.controller'
        self._base_plugin_classes = ControllerPlugin.get_plugins(
            search_pkg=base_plugin_pkg)

        self.sources = None
        self.chunker = None
        self.manager = None

        # Initialize configurations
        self._config = defaultdict(lambda: {})
        self._config.update(config_data.get('poller', {}))

        # Set controller configuration
        # run_once: ['gather', 'process'] tells the controller if the poller
        #           should query the devices and exit
        # period: the update timeout of the inventory
        # inventory_timeout: the maximum amount of time to wait for an
        #                    inventory from a source
        self._run_once = args.run_once
        self._period = args.update_period or \
            self._config.get('update-period', 3600)
        self._inventory_timeout = self._config.get('inventory_timeout', 10)

        # Validate the arguments
        self._validate_controller_args(args, config_data)

        # Get the inventory
        inventory_file = args.inventory or self._config['path']

        if inventory_file:
            if not Path(inventory_file).is_file():
                raise SqPollerConfError(
                    f'Inventory file not found at {inventory_file}'
                )
        else:
            raise SqPollerConfError(
                'No inventory file provided: use -I argument to provide it'
            )

        source_args = {'run-once': self._run_once,
                       'path': inventory_file}

        manager_args = {'run-once': self._run_once,
                        'exclude-services': args.exclude_services,
                        'no-colescer': args.no_coalescer,
                        'outputs': args.outputs,
                        'output-dir': args.output_dir,
                        'service-only': args.service_only,
                        'ssh-config-file': args.ssh_config_file,
                        'config-file': sq_get_config_file(args.config)}

        # Update configuration with command arguments
        self._config['source'].update(source_args)

        self._config['manager'].update(manager_args)
        if not self._config['manager'].get('type'):
            self._config['manager']['type'] = 'static_manager'

        if not self._config['chunker'].get('type'):
            self._config['chunker']['type'] = 'static_chunker'

    @property
    def run_once(self) -> str:
        """Returns the current working mode, wether it is gather or process.
        If None pollers will run forever.

        Returns:
            [str]: current run mode
        """
        return self._run_once

    @property
    def period(self) -> int:
        """Returns the update period of the inventory

        Returns:
            [int]: update period in seconds
        """
        return self._period

    @property
    def inventory_timeout(self) -> int:
        """Returns the maximum amount of time to wait for an inventory source
        retrieving its device list.

        Returns:
            int: inventory timeout in secodns
        """
        return self._inventory_timeout

    def init(self):
        """Loads the provider configuration and the plugins configurations
        and initialize all the plugins
        """

        # Initialize the controller modules
        logger.info('Initializing all the poller controller modules')

        logger.debug('Inizialing sources')

        self.sources = self.init_plugins('source')
        if not self.sources:
            raise SqPollerConfError('The inventory file has not any sources')

        # Initialize chunker module
        logger.debug('Initialize chunker module')

        chunkers = self.init_plugins('chunker')
        if len(chunkers) > 1:
            raise SqPollerConfError('Only 1 Chunker at a time is supported')
        self.chunker = chunkers[0]

        # initialize pollerManager
        logger.debug('Initialize manager module')

        managers = self.init_plugins('manager')
        if len(managers) > 1:
            raise SqPollerConfError(
                'Only 1 poller_manager at a time is supported'
            )
        self.manager = managers[0]

    def get_plugins_from_type(self, plugin_type: str) -> List[Type]:
        """Returns the list of plugins of type <plugin_type>

        Args:
            plugin_type (str): type of the plugins to be returned

        Returns:
            List[Type]: list of plugins of type <plugin_type>
        """
        return self._plugin_objects.get(plugin_type, None)

    def init_plugins(self, plugin_type: str) -> List[ControllerPlugin]:
        """Initialize the controller plugins of type <plugin_type> according
        to the controller configuration

        Args:
            plugin_type (str): type of plugins to initialize

        Raises:
            SqPollerConfError: raised if a wrong configuration is passed

        Returns:
            List[ControllerPlugin]: list of initialized plugins
        """
        plugin_conf = self._config.get(plugin_type) or {}

        base_plugin_class = self._base_plugin_classes.get(plugin_type, None)
        if not base_plugin_class:
            raise SqPollerConfError(f'Unknown plugin type {plugin_type}')

        # Initialize all the instances of the given plugin
        self._plugin_objects[plugin_type] = base_plugin_class.init_plugins(
            plugin_conf)
        return self._plugin_objects[plugin_type]

    async def run(self):
        """Start the device polling phase.

        In the kwargs are passed all the components that must be started

        Args:
            controller (Controller): contains the informations for controller
            and workers
        """
        # When the poller receives a termination signal, we would like
        # to gracefully terminate all the tasks
        loop = asyncio.get_event_loop()
        for s in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self._stop()))

        # Start collecting the tasks to launch
        source_tasks = [s.run() for s in self.sources
                        if isinstance(s, InventoryAsyncPlugin)]
        # Check if we need to launch the manager in background
        manager_tasks = []
        if isinstance(self.manager, InventoryAsyncPlugin):
            manager_tasks.append(self.manager.run())

        # Append the synchronization manager
        controller_task = [self._inventory_sync()]

        # Launch all the tasks
        tasks = [asyncio.create_task(t)
                 for t in (source_tasks + manager_tasks + controller_task)]
        try:
            while tasks:
                # TODO: fix this
                _, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )

                tasks = list(pending)
                # Ignore completed task if started with run_once
                if self.run_once:
                    continue

        except asyncio.CancelledError:
            logger.warning('Received termination signal, terminating...')

    def _stop(self):
        """Stop the controller"""

        tasks = [t for t in asyncio.all_tasks()
                 if t is not asyncio.current_task()]

        for task in tasks:
            task.cancel()

    async def _inventory_sync(self):
        while True:
            global_inventory = {}
            for inv_src in self.sources:
                try:
                    cur_inv = await asyncio.wait_for(
                        inv_src.get_inventory(),
                        self._inventory_timeout
                    )
                except asyncio.TimeoutError:
                    raise InventorySourceError(
                        f'Timeout error: source {inv_src.name} took'
                        'too much time'
                    )

                if cur_inv:
                    duplicated_devices = [x for x in cur_inv
                                          if x in global_inventory]
                    for dd in duplicated_devices:
                        logger.warning(f'Ignoring duplicated device {dd}')
                        cur_inv.pop(dd)

                global_inventory.update(cur_inv)

            n_pollers = self.manager.get_n_workers()

            inv_chunks = self.chunker.chunk(global_inventory, n_pollers)

            await self.manager.apply(inv_chunks)

            if self.run_once:
                break
            await asyncio.sleep(self._period)

    def _validate_controller_args(self, args: argparse.Namespace, cfg: Dict):
        """Validate the arguments given to the Controller instance

        Args:
            args (argparse.Namespace): the arguments given to the controller

        Raises:
            SqPollerConfError: raised if a wrong configuration is passed
        """
        # Check if the timeout and the period are valid
        if self._inventory_timeout < 1:
            raise SqPollerConfError(
                'Invalid inventory timeout: at least 1 second'
            )

        if self._period < 1:
            raise SqPollerConfError(
                'Invalid period: at least one second required'
            )

        # Check if service list is valid
        ServiceManager.get_service_list(
            args.service_only,
            args.exclude_services,
            cfg['service-directory']
        )
