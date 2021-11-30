"""This module manages and coordinates all the plugins

Classes:
    InventoryProvider: manages all the plugins

Functions:
    sq_main(): this function coordinates all the plugins initializing
                and starting each one of them. The plugins are divided
                in types. The supported types are:
                - basePlugins.InventorySource
                - basePlugins.Chunker
                - basePlugins.PollerManager
"""
from os.path import join, isfile
from typing import Type, List
import threading
import argparse
import yaml
from suzieq.inventoryProvider.utils \
    import INVENTORY_PROVIDER_PATH, get_class_by_path, get_classname_from_type


PLUGIN_PATH = join(INVENTORY_PROVIDER_PATH, "plugins")
BASE_PLUGIN_PATH = join(PLUGIN_PATH, "basePlugins")


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

    def load(self, config_data: dict):
        """Loads the provider configuration and the plugins configurations

        Args:
            config_data ([dict]): a dictionary which contains provider and
                                  plugins configurations
        """
        self._provider_config = config_data.get("provider_config", {})
        self._plugins_config = config_data.get("plugin_type", {})

    def get_plugins(self, plugin_type: str) -> List[Type]:
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
            RuntimeError: Invalid configuration
            RuntimeError: Unknown plugin
        """
        plugin_confs = self._plugins_config.get(plugin_type, {})
        if not plugin_confs:
            raise RuntimeError("No plugin configuration provided")

        # configure paths to reach the inventory plugins directories
        base_class_name = get_classname_from_type(plugin_type)
        ppath = join(PLUGIN_PATH, plugin_type)
        # Seach all the subclass of "base_class_name" inside "ppath"
        plugin_classes = get_class_by_path(
            ppath, BASE_PLUGIN_PATH, base_class_name
        )

        for plug_conf in plugin_confs:
            pname = plug_conf.get("plugin_name", "")
            if not pname:
                raise RuntimeError("Missing field <plugin_name>")
            if pname not in plugin_classes:
                raise RuntimeError(
                    f"Unknown plugin called {pname} with type {plugin_type}"
                )

            plugin = plugin_classes[pname](plug_conf.get("args", {}))
            if not self._plugin_objects.get(plugin_type, None):
                self._plugin_objects[plugin_type] = []
            self._plugin_objects[plugin_type].append(plugin)


def sq_prov_main():
    """InventoryProvider main function

    This function loads all the plugins provided in the configuration file and
    coordinates all the different plugins

    Raises:
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

    if config_file:
        if not isfile(config_file):
            raise RuntimeError(f"No configuration file at {config_file}")
        config_data = {}
        with open(
            config_file,
            "r",
            encoding="utf-8"
        ) as file:
            config_data = yaml.safe_load(file.read())

        inv_prov = InventoryProvider()
        inv_prov.load(config_data.get("inventory_provider", {}))

        inv_prov.init_plugins("inventorySource")

        inv_source_plugins = inv_prov.get_plugins("inventorySource")
        if not inv_source_plugins:
            raise RuntimeError(
                "No inventorySource plugin in the configuration file"
            )

        inv_source_threads = list()

        for is_plugin in inv_source_plugins:
            thead = threading.Thread(
                target=is_plugin.run,
                kwargs={"run_once": run_once}
            )
            inv_source_threads.append(thead)
            thead.start()

        for is_plugin in inv_source_plugins:
            print(is_plugin.get_inventory())


if __name__ == "__main__":
    sq_prov_main()
