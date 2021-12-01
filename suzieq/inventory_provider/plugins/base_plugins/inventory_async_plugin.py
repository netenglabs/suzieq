from abc import abstractmethod
from suzieq.shared.sq_plugin import SqPlugin


class InventoryAsyncPlugin(SqPlugin):
    @abstractmethod
    def run(self, **kwargs):
        pass

    @abstractmethod
    def stop(self):
        pass

