from inventoryProvider.plugins.basePlugins.inventorySource import InventorySource
from inventoryProvider.plugins.basePlugins.ipAsyncPlugin import IpAsyncPlugin

class NetboxInventory(InventorySource,IpAsyncPlugin):
    def __init__(self, input) -> None:
        super().__init__(input)

    def run(self):
        pass

    def stop(self):
        pass