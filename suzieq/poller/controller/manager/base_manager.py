"""This module contains the base class for a PollerManager.

Classes:
    PollerManager: The duty of a pollerManager is to manage pollers data
                   In some cases it can also monitor pollers
"""
from abc import abstractmethod
from typing import Dict, List
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin


class Manager(ControllerPlugin):
    """Manage and, in some cases, monitor pollers
    """

    @abstractmethod
    async def apply(self, inventory_chunks: Dict):
        """Apply the inventory chunks to the pollers

        Args:
            inventory_chunks (Dict): the portions of the global inventory
                                     to be passed to the poller
        """

    @abstractmethod
    async def launch_with_dir(self):
        """Launch a single poller writing the content of and input directory
        produced with the run-once=gather mode
        """

    @abstractmethod
    def get_n_workers(self, inventory: List[Dict]) -> int:
        """Given an inventory as input, return the required pollers to query
        all the devices in it.

        Args:
            inventory (List[Dict]): the inventory to be splitted across the
                                    poller instances

        Returns:
            int: number of desired workers
        """
    @classmethod
    def default_type(cls) -> str:
        return 'static'

    @classmethod
    def get_data_model(cls):
        """This is only temporary. In future release I will add manager
        validation via pydantic
        """
        raise NotImplementedError
