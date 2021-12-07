from abc import abstractmethod
from suzieq.shared.sq_plugin import SqPlugin


class InventoryAsyncPlugin(SqPlugin):
    """Plugins which inherit this class will have methods 'run' and 'stop'

    At the current version of suzieq, the controller if finds that a plugin
    has the 'run' method, it will call that method in a separate thread
    """
    @abstractmethod
    def run(self, **kwargs):
        """Task to be done after an initialization of a plugin"""

    @abstractmethod
    def stop(self):
        """Method to stop the 'run' method"""
