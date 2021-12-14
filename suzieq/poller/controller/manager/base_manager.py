"""This module contains the base class for a PollerManager.

Classes:
    PollerManager: The duty of a pollerManager is to manage pollers data
                   In some cases it can also monitor pollers
"""
from abc import abstractmethod
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin


class Manager(ControllerPlugin):
    """Manage and, in some cases, monitor pollers
    """

    @abstractmethod
    def apply(self, inventory_chunks):
        """Apply the inventory chunks on the pollers

        Args:
            inventory_chunks ([type]): the portions of the global inventory
                                       to be passed to the poller
        """

    @abstractmethod
    def get_n_workers(self, inventory) -> int:
        """Get the number of workers needed given the inventory

        Args:
            inventory ([type]): the inventory to be splitted across the poller
                                instances

        Returns:
            int: number of desired workers
        """
