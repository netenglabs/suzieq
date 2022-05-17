"""
This module contains the logic of the plugin
in charge of creating fake nodes returning
the the data inside an input directory
"""

from typing import Dict, List

from suzieq.poller.worker.inventory.inventory import Inventory
from suzieq.poller.worker.nodes.files import FileNode


class InputDirInventory(Inventory):
    """InputDirInventory is not a real inventory
    source plugin, but it is a debugging instrument,
    since it overrides the Inventory class in order to
    create fake nodes returning the content of the input
    directory
    """

    def __init__(self, add_task_fn, **kwargs) -> None:
        self.input_dir = kwargs.pop('input_dir', None)
        super().__init__(add_task_fn, **kwargs)

    async def build_inventory(self) -> Dict[str, FileNode]:
        """Returns a list containing a single fake node
        returning the data contained in the input directory

        Returns:
            Dict[str, FileNode]: a list containing all the nodes in the
                inventory
        """

        node = FileNode()
        await node.initialize(self.input_dir)
        self._nodes = {node.hostname: node}

        return self._nodes

    async def _get_device_list(self) -> List[Dict]:
        return []
