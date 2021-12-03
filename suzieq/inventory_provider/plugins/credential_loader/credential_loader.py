"""This module contains the base class for plugins which loads
devices credentials
"""
from abc import abstractmethod
from typing import Dict, List, Type
from suzieq.shared.sq_plugin import SqPlugin


class CredentialLoader(SqPlugin):
    """Base class used to import device credentials from different
    sources
    """

    def __init__(self, init_data) -> None:
        super().__init__()

        self._cred_format = [
            "username",
            "password",
            "key_path",
            "options"
        ]

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

    def write_credentials(self, device: Dict, credentials: Dict[str, Dict]):
        device["credentials"] = credentials
        missing_keys = self._validate_credentials(device)
        if missing_keys:
            raise ValueError(
                f"Invalid credentials: missing keys {missing_keys}")

    def _validate_credentials(self, device: Dict) -> List[str]:
        credentials = device.get("credentials", {})
        if not credentials:
            return ["credentials"]

        cred_keys = set(self._cred_format)
        for key in credentials.keys():
            if key in cred_keys:
                cred_keys.remove(key)

        # One between password or key_path must be defines
        if "password" in cred_keys and "key_path" in cred_keys:
            cred_keys.remove("password")
            cred_keys.remove("key_path")
            ret = list(cred_keys)
            ret.append("password or key_path")
            return ret

        if "password" in cred_keys:
            cred_keys.remove("password")

        if "key_path" in cred_keys:
            cred_keys.remove("key_path")

        return list(cred_keys)
