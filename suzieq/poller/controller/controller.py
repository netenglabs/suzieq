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
from suzieq.poller.controller.inventory_async_plugin \
    import InventoryAsyncPlugin
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin
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
        self._base_plugin_classes = ControllerPlugin.get_plugins(
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
        self._plugins_config = config_data

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
        plugin_conf = self._plugins_config.get(plugin_type) or {}
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

    def add_plugins_to_conf(self, plugin_type: str, plugin_data):
        """Add or override the content of plugins configuration with type <plugin_typ>

        Args:
            plugin_type (str): type of plugin to update
            plugin_data ([type]): data for plugin
        """
        self._plugins_config[plugin_type] = plugin_data


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

    config_data = load_sq_config(config_file=args.config)

    controller = Controller()
    controller.load(config_data.get("poller", {}))

    if inventory_file:
        if not isfile(inventory_file):
            raise RuntimeError(f"Inventory file not found at {inventory_file}")
        controller.add_plugins_to_conf(
            "source", {"path": inventory_file})

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
    manager = kwargs.pop("manager")
    inv_sources = kwargs.pop("inv_sources")
    run_once = kwargs.pop("run_once")

    # start inventorySources if needed
    for inv_src in inv_sources:
        if issubclass(type(inv_src), InventoryAsyncPlugin):
            thread = ControllerPluginThread(
                target=inv_src.run,
                kwargs={"run_once": run_once}
            )
            thread.start()
            inv_src.set_running_thread(thread)

    if issubclass(type(manager), InventoryAsyncPlugin):
        thread = ControllerPluginThread(
            target=manager.run,
            kwargs={"run_once": run_once}
        )
        thread.start()
        manager.set_running_thread(thread)

    while True:
        global_inventory = {}
        for inv_src in inv_sources:
            try:
                cur_inv = inv_src.get_inventory(
                    timeout=controller.timeout)
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

        n_pollers = manager.get_n_workers()

        inv_chunks = chunker.chunk(global_inventory, n_pollers)
        # TODO: handle manager thread errors
        manager.apply(inv_chunks)

        if run_once:
            break

        sleep(controller.period)


if __name__ == "__main__":
    sq_controller_main()
