"""
This module manages and coordinates all the plugins.

Classes:
    Controller: Manages all the plugins and coordinates their execution.

Functions:
    sq_main(): Coordinates the initialization and startup of all plugins, which are divided by type.
"""
import argparse
import asyncio
import logging
import signal
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
from copy import deepcopy

from suzieq.poller.controller.base_controller_plugin import ControllerPlugin
from suzieq.poller.controller.inventory_async_plugin import InventoryAsyncPlugin
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import sq_get_config_file

logger = logging.getLogger(__name__)

DEFAULT_INVENTORY_PATH = 'suzieq/config/etc/inventory.yaml'


class Controller:
    """Manages and coordinates all plugins specified in the configuration files."""

    def __init__(self, args: argparse.Namespace, config_data: dict) -> None:
        # Container for plugin objects, divided by type
        self._plugin_objects = {}

        # Collect basePlugin classes
        self._base_plugin_classes = ControllerPlugin.get_plugins()

        # Initialize the core components
        self.sources = []
        self.chunker = None
        self.manager = None
        self._config = defaultdict(lambda: {})
        self._config.update(config_data.get('poller', {}))

        # Controller configuration
        self._single_run_mode = args.run_once
        self._input_dir = args.input_dir
        if self._input_dir:
            self._single_run_mode = 'input-dir'

        # Debug mode adjusts the run behavior
        if args.debug:
            self._single_run_mode = 'debug'

        self._no_coalescer = args.no_coalescer
        if self._single_run_mode:
            self._no_coalescer = True

        # Set polling period and timeouts
        self._period = args.update_period or self._config.get('update-period', 3600)
        self._inventory_timeout = self._config.get('inventory-timeout', 10)
        self._n_workers = args.workers or self._config.get('manager', {}).get('workers', 1)

        # Validate configuration arguments
        self._validate_controller_args(args, config_data)

        # Setup inventory and manager configurations
        self._setup_inventory(args)
        self._setup_manager(args)

    def _setup_inventory(self, args: argparse.Namespace):
        """Sets up the inventory configuration and validates its existence."""
        default_inventory_file = DEFAULT_INVENTORY_PATH
        inventory_file = None

        if not self._input_dir:
            inventory_file = args.inventory or \
                self._config.get('inventory-file') or \
                default_inventory_file
            if not Path(inventory_file).is_file():
                raise SqPollerConfError(
                    f'Inventory file not found at {inventory_file}. Use -I argument to specify one.'
                )
        else:
            if not Path(self._input_dir).is_dir():
                raise SqPollerConfError(f'{self._input_dir} is not a valid directory')

    def _setup_manager(self, args: argparse.Namespace):
        """Sets up manager configuration based on command-line arguments and config data."""
        source_args = {
            'single-run-mode': self._single_run_mode,
            'path': DEFAULT_INVENTORY_PATH
        }

        manager_args = {
            'config': sq_get_config_file(args.config),
            'config-dict': self._config,
            'debug': args.debug,
            'input-dir': self._input_dir,
            'exclude-services': args.exclude_services,
            'no-coalescer': self._no_coalescer,
            'output-dir': args.output_dir,
            'outputs': args.outputs,
            'max-cmd-pipeline': self._config.get('max-cmd-pipeline', 0),
            'single-run-mode': self._single_run_mode,
            'run-once': args.run_once,
            'service-only': args.service_only,
            'ssh-config-file': args.ssh_config_file,
            'workers': self._n_workers
        }

        self._config['source'].update(source_args)
        self._config['manager'].update(manager_args)

    def _validate_controller_args(self, args: argparse.Namespace, cfg: Dict):
        """Validates the controller arguments to ensure correct configuration."""
        if self._inventory_timeout < 1:
            raise SqPollerConfError('Invalid inventory timeout: at least 1 second is required')

        if self._period < 1:
            raise SqPollerConfError('Invalid period: at least 1 second is required')

        if self._n_workers < 1:
            raise SqPollerConfError('At least one worker is required')

        ServiceManager.get_service_list(
            args.service_only,
            args.exclude_services,
            cfg['service-directory']
        )

    def init(self):
        """Initializes the controller, loading plugins and their configurations."""
        logger.info('Initializing poller controller modules')

        # Initialize sources and chunkers if not using an input directory
        if not self._input_dir:
            logger.debug('Initializing sources')
            self.sources = self.init_plugins('source')
            if not self.sources:
                raise SqPollerConfError('No source found in the inventory')

            logger.debug('Initializing chunker')
            chunkers = self.init_plugins('chunker')
            if len(chunkers) > 1:
                raise SqPollerConfError('Only one chunker at a time is supported')
            self.chunker = chunkers[0]

        logger.debug('Initializing manager')
        managers = self.init_plugins('manager')
        if len(managers) > 1:
            raise SqPollerConfError('Only one manager at a time is supported')
        self.manager = managers[0]

    def init_plugins(self, plugin_type: str) -> List[ControllerPlugin]:
        """Initializes the plugins of the specified type from the configuration."""
        plugin_conf = self._config.get(plugin_type) or {}

        base_plugin_class = self._base_plugin_classes.get(plugin_type, None)
        if not base_plugin_class:
            raise SqPollerConfError(f'Unknown plugin type: {plugin_type}')

        # Initialize and return plugins
        self._plugin_objects[plugin_type] = base_plugin_class.init_plugins(plugin_conf)
        return self._plugin_objects[plugin_type]

    async def run(self):
        """Starts the device polling phase and manages the lifecycle of tasks."""
        loop = asyncio.get_event_loop()
        for s in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(self._stop()))

        # Prepare tasks for execution
        source_tasks = [s.run() for s in self.sources if isinstance(s, InventoryAsyncPlugin)]
        manager_tasks = [self.manager.run()] if isinstance(self.manager, InventoryAsyncPlugin) else []
        controller_task = [self._inventory_sync()]

        # Launch all tasks asynchronously
        tasks = [asyncio.create_task(t) for t in (source_tasks + manager_tasks + controller_task)]
        try:
            while tasks:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = list(pending)
                for task in done:
                    if task.exception():
                        raise task.exception()

                if self._single_run_mode:
                    continue
        except asyncio.CancelledError:
            logger.warning('Received termination signal, terminating...')

    async def _stop(self):
        """Gracefully stops all running tasks."""
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()

    async def _inventory_sync(self):
        """Synchronizes the inventory and distributes it among workers."""
        if self._input_dir:
            await self.manager.launch_with_dir()
            return

        while True:
            global_inventory = {}

            for inv_src in self.sources:
                try:
                    cur_inv = deepcopy(await asyncio.wait_for(
                        inv_src.get_inventory(),
                        self._inventory_timeout
                    ))
                except asyncio.TimeoutError:
                    raise InventorySourceError(f'Timeout error: source {inv_src.name} took too long')

                logger.debug(f'Received inventory from {inv_src.name}')
                if cur_inv:
                    cur_inv_count = len(cur_inv)
                    duplicated_devices = [x for x in cur_inv
                                          if x in global_inventory]
                    for dd in duplicated_devices:
                        logger.warning(f'Ignoring duplicated device {dd}')
                        cur_inv.pop(dd)
                    if len(duplicated_devices) == cur_inv_count:
                        logger.warning(
                            f'All {inv_src.name} nodes have been ignored')
                else:
                    logger.warning(
                        f'source {inv_src.name} returned an empty inventory')

                global_inventory.update(cur_inv)

            if not global_inventory:
                raise InventorySourceError('No devices to poll')

            n_pollers = self.manager.get_n_workers(global_inventory)

            inventory_chunks = self.chunker.chunk(global_inventory, n_pollers)

            await self.manager.apply(inventory_chunks)

            if self._single_run_mode:
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

        if self._n_workers < 0:
            raise SqPollerConfError(
                'At least a worker is required'
            )

        # Check if service list is valid
        ServiceManager.get_service_list(
            args.service_only,
            args.exclude_services,
            cfg['service-directory']
        )
