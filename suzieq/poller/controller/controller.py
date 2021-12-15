"""This module manages and coordinates all the plugins

Classes:
    InventoryProvider: manages all the plugins

Functions:
    sq_main(): this function coordinates all the plugins initializing
                and starting each one of them. The plugins are divided
                in types.
"""
import argparse
from os.path import isfile
from typing import Type, List, Dict
from time import sleep
import threading
from suzieq.poller.controller.inventory_async_plugin \
    import InventoryAsyncPlugin
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin
from suzieq.shared.utils import sq_get_config_file


class Controller:
    """This class manages all the plugins set on the configuration files
    """

    def __init__(self, args: argparse.Namespace, config_data: dict) -> None:
        self._DEFAULT_PLUGINS = {
            "source": "file",
            "chunker": "static_chunker",
            "manager": "static_manager"
        }

        # containts the configuration data
        self._config = dict()

        # contains the Plugin objects divided by type
        self._plugin_objects = dict()

        self._period = 0
        self._timeout = 0
        self._run_once = False

        # collect basePlugin classes
        base_plugin_pkg = "suzieq.poller.controller"
        self._base_plugin_classes = ControllerPlugin.get_plugins(
            search_pkg=base_plugin_pkg)

        self.sources = None
        self.chunker = None
        self.manager = None

        self._args = args
        self._raw_config = config_data

    @property
    def run_once(self) -> bool:
        """Defines if the sources must be runned once.

        Attention: this will NOT call the run_once on pollers

        Returns:
            [bool]: run_once value
        """
        return self._run_once

    @run_once.setter
    def run_once(self, val: bool):
        self._run_once = val

    @property
    def period(self) -> int:
        """Defines how much time elapses before updating the global
        inventory

        Returns:
            [int]: sleep period
        """
        return self._period

    @period.setter
    def period(self, val: int):
        self._period = val

    @property
    def timeout(self) -> int:
        """Maximum time to wait on a InventorySource.get_inventor()

        Returns:
            int: inventory get timeot
        """
        return self._timeout

    @timeout.setter
    def timeout(self, val: int):
        self._timeout = val

    def init(self):
        """Loads the provider configuration and the plugins configurations
        and initialize all the plugins
        """
        source_args = {}
        chunker_args = {}
        manager_args = {}

        inventory_file = self._args.inventory
        self._run_once = self._args.run_once

        manager_args.update({"run-once": self._run_once})
        manager_args.update({"exclude-services": self._args.exclude_services})
        manager_args.update({"no-colescer": self._args.no_coalescer})
        manager_args.update({"outputs": self._args.outputs})
        manager_args.update({"output-dir": self._args.output_dir})
        manager_args.update({"service-only": self._args.service_only})
        manager_args.update({"ssh-config-file": self._args.ssh_config_file})
        manager_args.update(
            {"config-file": sq_get_config_file(self._args.config)})

        if inventory_file:
            if not isfile(inventory_file):
                raise RuntimeError(
                    f"Inventory file not found at {inventory_file}")
            source_args.update({"path": inventory_file})

        self._config = self.parse_poller_config(self._raw_config,
                                                source=source_args,
                                                chunker=chunker_args,
                                                manager=manager_args,
                                                run_once=self._run_once
                                                )

        self.period = self._config.get("period", 3600)
        self._timeout = self._config.get("timeout", 10)

        # initialize inventorySources
        self.init_plugins("source")

        self.sources = self.get_plugins_from_type("source")
        if not self.sources:
            raise RuntimeError(
                "No inventorySource plugin in the configuration file"
            )

        # initialize chunker
        self.init_plugins("chunker")
        chunkers = self.get_plugins_from_type("chunker")
        if len(chunkers) > 1:
            raise RuntimeError("Only 1 Chunker at a time is supported")
        self.chunker = chunkers[0]

        # initialize pollerManager
        self.init_plugins("manager")
        managers = self.get_plugins_from_type("manager")
        if len(managers) > 1:
            raise RuntimeError("Only 1 poller_manager at a time is supported")
        self.manager = managers[0]

    def parse_poller_config(self, config_data: dict, **kwargs) -> Dict:
        """Parse the config_data and generate the config

        Args:
            config_data (dict): raw config data

        Returns:
            [Dict]: config data
        """

        fields = ["source", "chunker", "manager"]
        controller_config = config_data.get("poller", {}).copy()

        for key, value in kwargs.items():
            if key in fields:
                # plugins configuration
                for k, v in value.items():
                    if not controller_config.get(key):
                        controller_config[key] = {}
                    controller_config[key][k] = v
            else:
                # controller/worker configuration
                controller_config[key] = value

        return controller_config

    def get_plugins_from_type(self, plugin_type: str) -> List[Type]:
        """Returns the list of plugins of type <plugin_type>

        Args:
            plugin_type (str): type of the plugins to be returned

        Returns:
            List[Type]: list of plugins of type <plugin_type>
        """
        return self._plugin_objects.get(plugin_type, None)

    def init_plugins(self, plugin_type: str):
        """Initialize all plugins of type <plugin_type>

        Args:
            plugin_type (str): type of plugins to initialize

        Raises:
            RuntimeError: No plugin configuration
            AttributeError: Invalid configuration
            RuntimeError: Unknown plugin
        """
        plugin_conf = self._config.get(plugin_type) or {}
        if not plugin_conf or not plugin_conf.get("type"):
            if plugin_type not in self._DEFAULT_PLUGINS:
                raise RuntimeError("No plugin configuration provided for "
                                   f"{plugin_type}")

            # Set the plugin_confs to load a the default configuration
            # of the plugin
            # Defualt plugins don't need any configuration
            plugin_conf.update({"type": self._DEFAULT_PLUGINS[plugin_type]})

        base_plugin_class = self._base_plugin_classes.get(plugin_type, None)
        if not base_plugin_class:
            raise AttributeError(f"Unknown plugin type {plugin_type}")

        plugins = base_plugin_class.init_plugins(plugin_conf)
        if not self._plugin_objects.get(plugin_type, None):
            self._plugin_objects[plugin_type] = []
        self._plugin_objects[plugin_type].extend(plugins)

    def run(self):
        """start the device polling phase.

        In the kwargs are passed all the components that must be started

        Args:
            controller (Controller): contains the informations for controller
            and workers
        """

        # start inventorySources if needed
        for inv_src in self.sources:
            if issubclass(type(inv_src), InventoryAsyncPlugin):
                thread = ControllerPluginThread(
                    target=inv_src.run,
                    kwargs={"run_once": self.run_once}
                )
                thread.start()
                inv_src.set_running_thread(thread)

        if issubclass(type(self.manager), InventoryAsyncPlugin):
            thread = ControllerPluginThread(
                target=self.manager.run,
                kwargs={"run_once": self.run_once}
            )
            thread.start()
            self.manager.set_running_thread(thread)

        while True:
            global_inventory = {}
            for inv_src in self.sources:
                try:
                    cur_inv = inv_src.get_inventory(
                        timeout=self.timeout)
                except TimeoutError as e:
                    exc_str = str(e)
                    if issubclass(type(inv_src), InventoryAsyncPlugin):
                        thread: ControllerPluginThread = \
                            inv_src.get_running_thread()
                        if thread and thread.exc:
                            exc_str += f"\n\nSource: {thread.exc}"
                    raise RuntimeError(exc_str)

                if cur_inv:
                    for device in cur_inv:
                        dev_name = device.get("id")
                        dev_ns = device.get("namespace")
                        global_inventory[f"{dev_ns}.{dev_name}"] = device

            n_pollers = self.manager.get_n_workers()

            inv_chunks = self.chunker.chunk(global_inventory, n_pollers)
            # TODO: handle manager thread errors
            self.manager.apply(inv_chunks)

            if self.run_once:
                break

            sleep(self.period)


class ControllerPluginThread(threading.Thread):
    """Custom thread class to handle thread exceptions
    """

    def run(self):
        # pylint: disable=attribute-defined-outside-init
        self.exc = None
        try:
            super().run()
        # pylint: disable=broad-except
        except Exception as e:
            self.exc = e
