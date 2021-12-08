"""This module manages and coordinates all the plugins

Classes:
    InventoryProvider: manages all the plugins

Functions:
    sq_main(): this function coordinates all the plugins initializing
                and starting each one of them. The plugins are divided
                in types.
"""
from os.path import isfile
from typing import Type, List
from time import sleep
import threading
import argparse
import yaml
from suzieq.poller.controller.inventory_async_plugin \
    import InventoryAsyncPlugin
from suzieq.shared.exceptions import InventorySourceError
from suzieq.shared.sq_plugin import SqPlugin
from suzieq.shared.utils import load_sq_config


class Controller:
    """This class manages all the plugins set on the configuration files
    """

    def __init__(self) -> None:
        self._DEFAULT_PLUGINS = {
            "source": "file",
            "chunker": "static_chunker",
            "manager": "static_manager"
        }
        self._controller_config = dict()

        # containts the configuration data
        # for each plugin
        self._plugins_config = dict()

        # contains the Plugin objects divided by type
        self._plugin_objects = dict()

        self._period = 0
        self._timeout = 0
        self._run_once = False

        # collect basePlugin classes
        base_plugin_pkg = "suzieq.poller.controller"
        self._base_plugin_classes = SqPlugin.get_plugins(
            search_pkg=base_plugin_pkg)

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

    def load(self, config_data: dict):
        """Loads the provider configuration and the plugins configurations

        Args:
            config_data ([dict]): a dictionary which contains provider and
                                  plugins configurations
        """
        self._plugins_config = config_data.get("plugin_type", {})

        self._controller_config = config_data.get("controller_config", {}) \
            or {}
        self.period = self._controller_config.get("period", 3600)
        self._timeout = self._controller_config.get(
            "timeout", 10
        )
        self._run_once = self._controller_config.get("run_once", False)

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
        plugin_confs = self._plugins_config.get(plugin_type, {})
        if not plugin_confs:
            raise RuntimeError("No plugin configuration provided for "
                               f"{plugin_type}")

        if not isinstance(plugin_confs, list):
            raise RuntimeError("Invalid plugin configurations for "
                               f"{plugin_type}: must be a list")

        base_plugin_class = self._base_plugin_classes.get(plugin_type, None)
        if not base_plugin_class:
            raise AttributeError(f"Unknown plugin type {plugin_type}")

        plugins_pkg = f"suzieq.poller.controller.{plugin_type}"
        plugin_classes = base_plugin_class.get_plugins(search_pkg=plugins_pkg)

        for plug_conf in plugin_confs:
            # load configuration from another file
            plugin_source_path = plug_conf.get("source_path")
            if plugin_source_path:
                plugin_confs.extend(
                    self._load_plugins_from_path(plugin_source_path))
                continue

            ptype = plug_conf.get(
                "type", self._DEFAULT_PLUGINS.get(plugin_type, ""))
            if not ptype:
                raise AttributeError(
                    "Missing field <type> and no default option")
            if ptype not in plugin_classes:
                raise RuntimeError(
                    f"Unknown plugin called {ptype} with type {plugin_type}"
                )

            plugin = plugin_classes[ptype](plug_conf)
            if not self._plugin_objects.get(plugin_type, None):
                self._plugin_objects[plugin_type] = []
            self._plugin_objects[plugin_type].append(plugin)

    def _load_plugins_from_path(self, source_path: str) -> Type:
        """Load the plugin from another file

        Args:
            source_path (str): file which contains plugin configuration

        Raises:
            RuntimeError: file doesn't exists

        Returns:
            [Type]: plugin configuration
        """
        # TODO: right now the only supported format is yaml.
        # We need to find a way to import also json

        if not isfile(source_path):
            raise RuntimeError(f"File {source_path} doesn't exists")

        plugins_data = []
        with open(source_path, "r") as fp:
            file_content = fp.read()
            try:
                plugins_data = yaml.safe_load(file_content)
            except Exception as e:
                raise InventorySourceError('Invalid Suzieq inventory '
                                           f'file: {e}')

        return plugins_data

    def add_plugins_to_conf(self, plugin_type: str, plugin_data):
        """Add or override the content of plugins configuration with type <plugin_typ>

        Args:
            plugin_type (str): type of plugin to update
            plugin_data ([type]): data for plugin
        """
        self._plugins_config[plugin_type] = plugin_data


def sq_controller_main():
    """Controller main function

    This function loads all the plugins provided in the configuration file and
    coordinates all the different plugins

    Raises:
        RuntimeError: Invalid configuration file passed as parameter
        RuntimeError: Cannot find the configuration file
        RuntimeError: Missing inventorySource plugins in the configuration
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-c",
        "--config",
        help="Controller configuration file",
        type=str
    )

    parser.add_argument(
        "-r",
        "--run-once",
        action='store_true',
        help="Run inventory sources only once"
    )

    parser.add_argument(
        "-I",
        "--inventory",
        help="Input inventory file",
        type=str
    )

    args = parser.parse_args()

    run_once = args.run_once
    inventory_file = args.inventory

    config_data = load_sq_config(args.config)

    controller = Controller()
    controller.load(config_data.get("controller", {}))

    if inventory_file:
        if not isfile(inventory_file):
            raise RuntimeError(f"Inventory file not found at {inventory_file}")
        controller.add_plugins_to_conf(
            "source", [{"source_path": inventory_file}])

    # initialize inventorySources
    controller.init_plugins("source")

    inv_sources = controller.get_plugins_from_type("source")
    if not inv_sources:
        raise RuntimeError(
            "No inventorySource plugin in the configuration file"
        )

    # initialize chunker
    controller.init_plugins("chunker")
    chunkers = controller.get_plugins_from_type("chunker")
    if len(chunkers) > 1:
        raise RuntimeError("Only 1 Chunker at a time is supported")
    chunker = chunkers[0]

    # initialize pollerManager
    controller.init_plugins("manager")
    managers = controller.get_plugins_from_type("manager")
    if len(managers) > 1:
        raise RuntimeError("Only 1 poller_manager at a time is supported")
    manager = managers[0]

    start_polling(controller,
                  chunker=chunker,
                  manager=manager,
                  inv_sources=inv_sources,
                  run_once=run_once or controller.run_once
                  )


def start_polling(controller: Controller, **kwargs):
    """start the polling phase.

    In the kwargs are passed all the components that must be started

    Args:
        controller (Controller): contains the informations for controller
        and workers
    """
    chunker = kwargs.pop("chunker")
    poller_manager = kwargs.pop("manager")
    inv_sources = kwargs.pop("inv_sources")
    run_once = kwargs.pop("run_once")

    # start inventorySources if needed
    for inv_src in inv_sources:
        if issubclass(type(inv_src), InventoryAsyncPlugin):
            thread = threading.Thread(
                target=inv_src.run,
                kwargs={"run_once": run_once}
            )
            thread.start()

    if issubclass(type(poller_manager), InventoryAsyncPlugin):
        pm_thread = threading.Thread(
            target=poller_manager.run,
            kwargs={"run_once": run_once}
        )
        pm_thread.start()

    while True:
        global_inventory = {}
        for inv_src in inv_sources:
            cur_inv = inv_src.get_inventory(
                timeout=controller.timeout)
            if cur_inv:
                for device in cur_inv:
                    dev_name = device.get("id")
                    dev_ns = device.get("namespace")
                    global_inventory[f"{dev_ns}.{dev_name}"] = device

        n_pollers = poller_manager.get_pollers_number()

        inv_chunks = chunker.chunk(global_inventory, n_pollers)
        poller_manager.apply(inv_chunks)

        if run_once:
            break

        sleep(controller.period)


if __name__ == "__main__":
    sq_controller_main()
