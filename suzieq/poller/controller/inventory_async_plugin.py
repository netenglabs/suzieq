from abc import abstractmethod
from suzieq.shared.sq_plugin import SqPlugin


class InventoryAsyncPlugin(SqPlugin):
    """Plugins which inherit this class will have methods 'run'

    Once the controller check that the object inherit this class, it launches
    a new task executing the run method.
    """

    async def run(self):
        """Background task to launch in order to execute the plugin"""
        try:
            await self._execute()
        finally:
            await self._stop()

    @abstractmethod
    async def _execute(self):
        """Launch the backuground task
        """

    async def _stop(self):
        """Actions to execute before terminating the task
        """
        return
