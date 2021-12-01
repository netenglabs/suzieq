"""Module containing base class for inventorySource plugins
"""
from abc import abstractmethod
from copy import copy
from threading import Semaphore
from typing import Dict, Type
from suzieq.inventory_provider.plugins.inventory_source.credential_loader\
    .credential_loader import CredentialLoader
from suzieq.shared.sq_plugin import SqPlugin


class InventorySource(SqPlugin):
    """Base class for plugins which reads inventories"""

    def __init__(self, input_data) -> None:
        super().__init__()

        self._inv_semaphore = Semaphore()
        self._inventory = {}
        self._inv_is_set = False
        self._inv_is_set_sem = Semaphore()
        self._inv_is_set_sem.acquire()

        self._inv_formatter = {
            "hostname": "hostname",
            "namespace": "namespace",
            "ipv4": "ipv4",
            "ipv6": "ipv6",
            "credentials": "credentials"
        }

        self._load(input_data)
        errors = self._validate_config()
        if errors:
            raise RuntimeError("Inventory validation failed: {}"
                               .format(errors))

        self._update_inventory_format()

    @abstractmethod
    def _load(self, input_data):
        """Store informations from raw data"""

    @abstractmethod
    def _validate_config(self):
        """Checks if the loaded data is valid or not"""

    def get_inventory(self, timeout: int = 10) -> Dict[str, Dict]:
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
            Dict[str, Dict]: the inventory
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

        if callable(getattr(self._inventory, "copy", None)):
            inventory_snapshot = self._inventory.copy()
        else:
            inventory_snapshot = copy(self._inventory)
        self._inv_semaphore.release()
        return inventory_snapshot

    def set_inventory(self, new_inventory: dict, timeout: int = 10):
        """Set the inventory in a thread safe way

        The function will try to set the inventory until the timeout
        expires.

        Before setting the new inventory, it calls the formatter

        Args:
            new_inventory ([dict]): new inventory to set
            timeout (int, optional): maximum amount of time to wait.
            Defaults to 10.

        Raises:
            TimeoutError: unable to acquire the lock before the timeout
            expires
        """
        formatted_inventory = self._format_inventory(new_inventory)
        ok = self._inv_semaphore.acquire(timeout=timeout)
        if not ok:
            raise TimeoutError(
                "Unable to acquire the lock before the timeout expiration"
            )

        if callable(getattr(self._inventory, "copy", None)):
            new_inventory_copy = formatted_inventory.copy()
        else:
            new_inventory_copy = copy(formatted_inventory)
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
        cred_loader_pkg = "suzieq.inventory_provider.plugins.inventory_source"\
            ".credential_loader"
        l_classes = CredentialLoader.get_plugins(cred_loader_pkg)

        if l_classes:
            return l_classes.get(ltype, None)
        return None

    def _update_inventory_format(self, input_inv_format: dict = None):
        """update the inventory format

        The inventory format is used to specify how to adjust the data
        retrieved from the source and produce an output common to all
        sources.

        This function must be overrided if the data format is different from
        the default one.

        Raises:
            AttributeError: Invalid key for the formatter

        Args:
            input_inv_format (dict, optional): new format to apply. If
            the dictionary is empty or not provided the function is skipped.
            Default to None.
        """
        if input_inv_format:
            for input_key, input_value in input_inv_format.items():
                if input_key in self._inv_formatter:
                    self._inv_formatter[input_key] = input_value
                else:
                    raise AttributeError(f"Invalid key {input_key} for "
                                         "formatter")

    def _format_inventory(self, inventory: Dict[str, Dict]) -> Dict[str, Dict]:
        """this function formats the inventory following the inventory
        formatter

        Args:
            inventory (Dict[str, Dict]): inventory to format

        Raises:
            AttributeError: Invaid formatter

        Returns:
            Dict[str,Dict]: formatted inventory
        """
        out_inventory = {}
        for dev_name, device in inventory.items():
            out_inventory[dev_name] = {}
            for out_key, dev_key in self._inv_formatter.items():
                out_inventory[dev_name][out_key] = device.get(dev_key, None)

        return out_inventory
