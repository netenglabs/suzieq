"""Module containing base class for inventorySource plugins
"""
from abc import abstractmethod
from copy import copy
from threading import Semaphore
from typing import Dict, Type, List
from suzieq.inventory_provider.plugins.credential_loader\
    .credential_loader import CredentialLoader
from suzieq.shared.sq_plugin import SqPlugin


class InventorySource(SqPlugin):
    """Base class for plugins which reads inventories"""

    def __init__(self, input_data) -> None:
        super().__init__()

        self._inv_semaphore = Semaphore()
        self._inventory = []
        self._inv_is_set = False
        self._inv_is_set_sem = Semaphore()
        self._inv_is_set_sem.acquire()

        self._inv_format = [
            "hostname",
            "namespace",
            "ipv4",
            "ipv6",
            "credentials"
        ]

        self._load(input_data)
        errors = self._validate_config()
        if errors:
            raise RuntimeError("Inventory validation failed: {}"
                               .format(errors))

    @abstractmethod
    def _load(self, input_data):
        """Store informations from raw data"""

    @abstractmethod
    def _validate_config(self):
        """Checks if the loaded data is valid or not"""

    def get_inventory(self, timeout: int = 10) -> List[Dict]:
        """Retrieve the inventory in a thread safe way

        If the result was not yet produced, the function will wait until the
        timeout expires

        If the result was produced but the inventory is not accessible because
        the lock is kept by another thread, the function will wait until the
        timeout expires

        Args:
            timeout (int, optional): maximum amount of time to wait.
            Defaults to 10.

        Raises:
            ValueError: negative timeout argument
            TimeoutError: unable to acquire the lock before the timeout
            expires

        Returns:
            List[Dict]: inventory devices
        """

        if timeout < 0:
            raise ValueError(
                "timeout value must be positive, found {}".format(timeout)
            )

        ok = self._inv_is_set_sem.acquire(timeout=timeout)
        if not ok:
            raise TimeoutError(
                "Unable to acquire the lock before the timeout expiration"
            )
        self._inv_is_set_sem.release()
        ok = self._inv_semaphore.acquire(timeout=timeout)
        if not ok:
            raise TimeoutError(
                "Unable to acquire the lock before the timeout expiration"
            )

        inventory_snapshot = copy(self._inventory)
        self._inv_semaphore.release()
        return inventory_snapshot

    def set_inventory(self, new_inventory: List[Dict], timeout: int = 10):
        """Set the inventory in a thread safe way

        The function will try to set the inventory until the timeout
        expires.

        Before setting the new inventory, it calls the validator.
        If the new_inventory is not int the format 

        Args:
            new_inventory ([List[Dict]]): new inventory to set
            timeout (int, optional): maximum amount of time to wait.
            Defaults to 10.

        Raises:
            TimeoutError: unable to acquire the lock before the timeout
            expires
        """
        missing_keys = self._is_invalid_inventory(new_inventory)
        if missing_keys:
            raise ValueError(f"Invalid inventory: missing keys {missing_keys}")
        ok = self._inv_semaphore.acquire(timeout=timeout)
        if not ok:
            raise TimeoutError(
                "Unable to acquire the lock before the timeout expiration"
            )

        new_inventory_copy = copy(new_inventory)
        self._inventory = new_inventory_copy
        if not self._inv_is_set:
            # the inventory has been set for the first time
            self._inv_is_set = True
            self._inv_is_set_sem.release()
        self._inv_semaphore.release()

    def _get_loader_class(self, ltype: str) -> Type:
        """Returns the credential loader class from the type

        Args:
            ltype ([str]): credential loader type

        Returns:
            Type: credential loader class
        """
        cred_loader_pkg = "suzieq.inventory_provider.plugins.credential_loader"
        l_classes = CredentialLoader.get_plugins(search_pkg=cred_loader_pkg)

        if l_classes:
            return l_classes.get(ltype, None)
        return None

    def _is_invalid_inventory(self, inventory: List[Dict]) -> List[str]:
        """Validate the inventory

        The goal of this function is to check that all the devices has all
        the values in self._inv_format

        This function is called inside the set_inventory

        Args:
            inventory (List[Dict]): inventory to validate

        Returns:
            List[str]: list of missing fields
        """
        for device in inventory:
            device_keys = set(self._inv_format)
            for key in device.keys():
                if key in device_keys:
                    device_keys.remove(key)
            if device_keys:
                return list(device_keys)
        return []
