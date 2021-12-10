from abc import abstractmethod
import threading
from suzieq.shared.sq_plugin import SqPlugin


class InventoryAsyncPlugin(SqPlugin):
    """Plugins which inherit this class will have methods 'run' and 'stop'

    At the current version of suzieq, the controller if finds that a plugin
    has the 'run' method, it will call that method in a separate thread
    """
    def __init__(self) -> None:
        self._thread = None
        super().__init__()

    def set_running_thread(self, thread: threading.Thread):
        """Set the thread on which the plugin is running

        This function is not mandatory.
        An InventoryAsyncPlugin can be used in a single thread environment

        Args:
            thread (threading.Thread): plugin's running thread
        """
        self._thread = thread

    def get_running_thread(self) -> threading.Thread:
        """Return the thread on which the plugin is running

        Returns:
            threading.Thread: plugin's running thread
        """
        return self._thread

    @abstractmethod
    def run(self, **kwargs):
        """Task to be done after an initialization of a plugin"""

    @abstractmethod
    def stop(self):
        """Method to stop the 'run' method"""
