from abc import abstractmethod


class InventoryAsyncPlugin:
    @abstractmethod
    def run(self, **kwargs):
        pass

    @abstractmethod
    def stop(self):
        pass

