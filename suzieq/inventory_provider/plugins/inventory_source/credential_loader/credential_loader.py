"""This module contains the base class for plugins which loads
devices credentials
"""
from abc import abstractmethod
from typing import Dict, Type
from suzieq.shared.sq_plugin import SqPlugin


class CredentialLoader(SqPlugin):
    """Base class used to import device credentials from different
    sources
    """
    def __init__(self, init_data) -> None:
        super().__init__()
        self.init(init_data)

    def init(self, init_data: Type):
        """Initialize the object

        Args:
            init_data (Type): data used to initialize the object
        """

    @abstractmethod
    def load(self, inventory: Dict[str, Dict]):
        """Loads the credentials inside the inventory

        Args:
            inventory (Dict[str, Dict]): inventory to update
        """
