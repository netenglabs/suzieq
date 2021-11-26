import yaml
from suzieq.inventoryProvider.utils \
    import INVENTORY_PROVIDER_PATH, get_class_by_path, get_classname_from_type
from os.path import join
import threading
import argparse


PLUGIN_PATH = join(INVENTORY_PROVIDER_PATH, "plugins")
BASE_PLUGIN_PATH = join(PLUGIN_PATH, "basePlugins")


class InventoryProvider:
    def __init__(self) -> None:
        self._provider_config = dict()

        # containts the configuration data
        # for each plugin
        self._plugins_config = dict()

        # contains the Plugin objects divided by type
        self._plugin_objects = dict()

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
        base_class_name = get_classname_from_type(plugin_type)
        ppath = join(PLUGIN_PATH, plugin_type)
        # Seach all the subclass of "base_class_name" inside "ppath"
        plugin_classes = get_class_by_path(
            ppath, BASE_PLUGIN_PATH, base_class_name
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
