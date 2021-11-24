import yaml
from suzieq.inventoryProvider.utils import get_class_by_path
from os.path import dirname, abspath
from inspect import getfile
import threading
import argparse


def get_classname_from_ptype(plugin_type: str):
    """
    Return the name of a class starting from its type

    example:
    plugin_type = chunker -> class = Chunker
    """
    if len(plugin_type) > 1:
        return plugin_type[0].upper() + plugin_type[1:]


class InventoryProvider:
    def __init__(self) -> None:
        self._provider_config = dict()

        # containts the configuration data
        # for each plugin
        self._plugins_config = dict()

        # contains the Plugin objects divided by type
        self._plugin_objects = dict()

        # constant with the path to the inventoryProvider directory
        self._INVENTORY_PROVIDER_PATH = abspath(
            dirname(getfile(InventoryProvider))
        )

    def load(self, config_data):
        self._provider_config = config_data.get("provider_config", {})
        self._plugins_config = config_data.get("plugin_type", {})

    def get_plugins(self, plugin_type):
        return self._plugin_objects.get(plugin_type, None)

    def init_plugins(self, plugin_type):
        plugin_confs = self._plugins_config.get(plugin_type, {})
        if not plugin_confs:
            raise RuntimeError("No plugin configuration provided")

        # configure paths to reach the inventory plugins directories
        pmodule = f"suzieq.inventoryProvider.plugins.{plugin_type}"
        base_class_module = (
            f"suzieq.inventoryProvider.plugins.basePlugins.{plugin_type}"
        )
        base_class_name = get_classname_from_ptype(plugin_type)
        ppath = "{}/plugins/{}"\
                .format(self._INVENTORY_PROVIDER_PATH, plugin_type)
        # plugin_classes contains all the plugins in "pclass_path"
        # of type "class_type_name"
        plugin_classes = get_class_by_path(
            pmodule, ppath, base_class_module, base_class_name
        )

        for pc in plugin_confs:
            pname = pc.get("plugin_name", "")
            if not pname:
                raise RuntimeError("Missing field <plugin_name>")
            if pname not in plugin_classes:
                raise RuntimeError(
                    "Unknown plugin called {} with type {}"
                    .format(pname, plugin_type)
                )

            plugin = plugin_classes[pname](pc.get("args", {}))
            if not self._plugin_objects.get(plugin_type, None):
                self._plugin_objects[plugin_type] = []
            self._plugin_objects[plugin_type].append(plugin)


def sq_prov_main():

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

        config_data = {}
        with open(
            config_file,
            "r",
        ) as fp:
            file_data = fp.read()
            config_data = yaml.safe_load(file_data)

        ni = InventoryProvider()
        ni.load(config_data.get("inventory_provider", {}))

        ni.init_plugins("inventorySource")

        invSrc_plugins = ni.get_plugins("inventorySource")
        if not invSrc_plugins:
            raise RuntimeError(
                "No inventorySource plugin in the configuration file"
            )

        invSrc_threads = list()

        for p in invSrc_plugins:
            t = threading.Thread(target=p.run, kwargs={"run_once": run_once})
            invSrc_threads.append(t)
            t.start()

        for p in invSrc_plugins:
            print(p.get_inventory())


if __name__ == "__main__":
    sq_prov_main()
