"""StaticPollerManager module

    This module contains a simple PollerManager which only writes
    inventory chunks on different files for the pollers
"""
from typing import List, Dict
from suzieq.inventoryProvider.plugins.basePlugins.poller_manager \
    import PollerManager


class StaticPollerManager(PollerManager):
    """The StaticPollerManager writes the inventory chunks on files

    The number of pollers is defined in the configuration file with
    the path for inventory files
    """
    def __init__(self, config_data):

        if not config_data:
            raise ValueError("No configuration provided")

        self._pollers_count = config_data.get("pollers_count", 1)
        self._inventory_path = config_data.get("inventory_path", "")
        self._inventory_file_name = config_data \
            .get("inventory_file_name", "inventory")

    def apply(self, inventory_chunks: List[Dict]):
        """Write inventory chunks on files

        Args:
            inventory_chunks (List[Dict]): input inventory chunks
        """
        # I'm waiting if the new format for the yaml inventory is approved
        raise NotImplementedError

    def get_pollers_number(self, inventory: dict = None) -> int:
        """returns the content of self._poller_count statically loaded from
           the configuration file

        Attention: This function doesn't use the inventory

        Args:
            inventory (dict, optional): The global inventory.

        Returns:
            int: number of desired pollers configured in the configuration
                 file
        """
        return self._pollers_count
