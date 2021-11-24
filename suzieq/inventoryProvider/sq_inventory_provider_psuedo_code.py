import threading


class InventoryProvider:
    def __init__(self) -> None:
        self._provider_config = dict()

        # containts the configuration data
        # for each plugin
        self._plugins_config = dict()

        # contains the Plugin objects divided by type
        self._plugin_objects = dict()

    def load(self, config_data):
        self._provider_config = config_data["provider_config"]
        self._plugins_config = config_data["plugin_type"]

    def get_plugins(self, plugin_type):
        return self._plugin_objects[plugin_type]

    def init_plugins(self, plugin_type):
        plugin_confs: list = self._plugins_config[plugin_type]

        for pc in plugin_confs:
            # create a plugin depending on the pc["plugin_name"]
            plugin = Plugin(pc["plugin_name"])
            # init the plugin using pc["args"]
            plugin.init(pc["args"])

            self._plugin_objects[plugin_type].append(plugin)

    def run_plugins(self, plugin_type):
        plugins: list = self._plugin_objects[plugin_type]

        # start in a new thread the "run" function for each plugin
        for p in plugins:
            threading.Thread(p.run()).start()

    def get_source_inventories(self):
        plugins: list = self._plugin_objects["source"]

        inventories = []

        for p in plugins:
            inventories.append(p.get_inventory())

        return inventories


def inv_provider_main():

    # load the configuration inside the InventoryProvider class
    inv_prov = InventoryProvider()
    config = load_config_file(configFilePath)
    inv_prov.load(config)

    # init pollerManager
    inv_prov.init_plugins("pollerManager")
    pollMng = inv_prov.get_plugins("pollerManager")
    if len(pollMng) != 1:
        # error: only 1 pollerManager is supported
        return
    pollMng = pollMng[0]

    # init chunker
    inv_prov.init_plugins("chunker")
    chunker = inv_prov.get_plugins("chunker")
    if len(chunker) != 1:
        # error: only 1 chunker is supported
        return
    chunker = chunker[0]

    # init source plugins
    inv_prov.init_plugins("source")

    # run source plugins
    inv_prov.run_plugins("source")

    old_global_inventory_hash = None

    while True:

        # get source plugins inventories
        inventories: list = inv_prov.get_source_inventories()

        # join source inventories in the global inventory
        global_inventory = joinInventories(inventories)
        current_global_inventory_hash = hash(global_inventory)

        if current_global_inventory_hash != old_global_inventory_hash:
            # give the global inventory to the pollerManager to retrieve the number of chunks
            n_chunks = pollMng.get_pollers_number(global_inventory)

            # give the global inventory to the chunker and wait for chunks
            inventory_chunks: list = chunker.chunk(global_inventory, n_chunks)

            # give the inventory chunks to the pollerManager
            pollMng.apply(inventory_chunks)

            old_global_inventory_hash = current_global_inventory_hash

        if params.run_once:
            break

        sleep(inv_prov._provider_config["period"])


if __name__ == "__main__":
    inv_provider_main()
