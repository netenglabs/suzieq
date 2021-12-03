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
from suzieq.inventory_provider.plugins.inventory_async_plugin \
    import InventoryAsyncPlugin
from suzieq.shared.sq_plugin import SqPlugin


class InventoryProvider:
    """This class manages all the plugins set on the configuration files
    """

    def __init__(self) -> None:
        self._provider_config = dict()

        # containts the configuration data
        # for each plugin
        self._plugins_config = dict()

        # contains the Plugin objects divided by type
        self._plugin_objects = dict()

        self._period = 0
        self._inv_get_timeout = 0

        # collect basePlugin classes
        base_plugin_pkg = "suzieq.inventory_provider.plugins"
        self._base_plugin_classes = SqPlugin.get_plugins(
            search_pkg=base_plugin_pkg)

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
    def inv_get_timeout(self) -> int:
        """Maximum time to wait on a InventorySource.get_inventor()

        Returns:
            int: inventory get timeot
        """
        return self._inv_get_timeout

    @inv_get_timeout.setter
    def inv_get_timeout(self, val: int):
        self._inv_get_timeout = val

    def load(self, config_data: dict):
        """Loads the provider configuration and the plugins configurations

        Args:
            config_data ([dict]): a dictionary which contains provider and
                                  plugins configurations
        """
        self._plugins_config = config_data.get("plugin_type", {})

        self._provider_config = config_data.get("provider_config", {})
        self.period = self._provider_config.get("period", 3600)
        self._inv_get_timeout = self._provider_config.get(
            "inventory_get_timeout", 10
        )

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

        # # configure paths to reach the inventory plugins directories
        # base_class_name = get_classname_from_type(plugin_type)
        # ppath = join(PLUGIN_PATH, plugin_type)
        # # Seach all the subclass of "base_class_name" inside "ppath"
        # plugin_classes = get_class_by_path(
        #     ppath, BASE_PLUGIN_PATH, base_class_name
        # )

        base_plugin_class = self._base_plugin_classes.get(plugin_type, None)
        if not base_plugin_class:
            raise AttributeError(f"Unknown plugin type {plugin_type}")

        plugins_pkg = f"suzieq.inventory_provider.plugins.{plugin_type}"
        plugin_classes = base_plugin_class.get_plugins(search_pkg=plugins_pkg)

        for plug_conf in plugin_confs:
            pname = plug_conf.get("plugin_name", "")
            if not pname:
                raise AttributeError("Missing field <plugin_name>")
            if pname not in plugin_classes:
                raise RuntimeError(
                    f"Unknown plugin called {pname} with type {plugin_type}"
                )

            plugin = plugin_classes[pname](plug_conf.get("args", None))
            if not self._plugin_objects.get(plugin_type, None):
                self._plugin_objects[plugin_type] = []
            self._plugin_objects[plugin_type].append(plugin)


def sq_prov_main():
    """InventoryProvider main function

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
        help="InventoryProvider configuration file",
        required=True
    )

    parser.add_argument(
        "-r",
        "--run-once",
        action='store_true',
        help="Run inventory sources only once"
    )

    args = parser.parse_args()

    config_file = args.config
    run_once = args.run_once

    if not config_file:
        raise RuntimeError("Invalid -c/--config parameter value")

    if not isfile(config_file):
        raise RuntimeError(f"No configuration file at {config_file}")
    config_data = {}
    with open(
        config_file, "r"
    ) as file:
        config_data = yaml.safe_load(file.read())

    inv_prov = InventoryProvider()
    inv_prov.load(config_data.get("inventory_provider", {}))

    # initialize inventorySources
    inv_prov.init_plugins("inventory_source")

    inv_source_plugins = inv_prov.get_plugins_from_type("inventory_source")
    if not inv_source_plugins:
        raise RuntimeError(
            "No inventorySource plugin in the configuration file"
        )

    inv_source_threads = []
    # start inventorySources if needed
    for inv_src_plugin in inv_source_plugins:
        if issubclass(type(inv_src_plugin), InventoryAsyncPlugin):
            thread = threading.Thread(
                target=inv_src_plugin.run,
                kwargs={"run_once": run_once}
            )
            inv_source_threads.append(thread)
            thread.start()

    # initialize chunker
    inv_prov.init_plugins("chunker")
    chunkers = inv_prov.get_plugins_from_type("chunker")
    if len(chunkers) > 1:
        raise RuntimeError("Only 1 Chunker at a time is supported")
    chunker = chunkers[0]

    # initialize pollerManager
    inv_prov.init_plugins("poller_manager")
    poller_managers = inv_prov.get_plugins_from_type("poller_manager")
    if len(poller_managers) > 1:
        raise RuntimeError("Only 1 poller_manager at a time is supported")
    poller_manager = poller_managers[0]
    pm_thread = None
    if issubclass(type(poller_manager), InventoryAsyncPlugin):
        pm_thread = threading.Thread(
            target=poller_manager.run,
            kwargs={"run_once": run_once}
        )
        pm_thread.start()

    while True:
        global_inventory = {}
        for inv_src_plugin in inv_source_plugins:
            cur_inv = inv_src_plugin.get_inventory(
                timeout=inv_prov.inv_get_timeout)
            print(cur_inv)
            if cur_inv:
                for device in cur_inv:
                    dev_name = device.get("hostname")
                    dev_ns = device.get("namespace")
                    global_inventory[f"{dev_ns}.{dev_name}"] = device

        n_pollers = poller_manager.get_pollers_number()

        inv_chunks = chunker.chunk(global_inventory, n_pollers)
        for ic in inv_chunks:
            print(ic, end="\n----\n")

        poller_manager.apply(inv_chunks)

        if run_once:
            break

        print("sleeping for", inv_prov.period)
        sleep(inv_prov.period)


if __name__ == "__main__":
    sq_prov_main()
