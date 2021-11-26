from abc import abstractmethod
from copy import copy
from threading import Semaphore
from suzieq.inventoryProvider.plugins.inventorySource.credentialLoader\
    .credentialLoader import CredentialLoader
from suzieq.inventoryProvider.utils import get_class_by_path
from inspect import getfile
from os.path import abspath, dirname


class InventorySource:
    def __init__(self, input_data) -> None:
        """
        - Saves inside a data structure the raw content of <input>
        - Calls self.load
        - Calls self.validate_data
        """
        self._inv_semaphore = Semaphore()
        self._inventory = {}
        self._inv_is_set = False
        self._inv_is_set_sem = Semaphore()
        self._inv_is_set_sem.acquire()

        self._load(input_data)
        errors = self._validate_config()
        if errors:
            raise RuntimeError("Inventory validation failed: {}"
                               .format(errors))

    @abstractmethod
    def _load(self, input_data):
        """Store important informations from raw data"""
        pass

    @abstractmethod
    def _validate_config(self):
        """Checks if the loaded data is valid or not"""
        pass

    def get_inventory(self, timeout: int = 10):
        """
        - Acquire semaphore
        - Copy inventory
        - Release semaphore
        - Return inventory
        """

        if timeout < 0:
            return None, ValueError(
                "timeout value must be positive, found {}".format(timeout)
                )

        ok = self._inv_is_set_sem.acquire(timeout=timeout)
        if not ok:
            return None, TimeoutError(
                "Unable to acquire the lock before the timeout expiration"
            )
        ok = self._inv_semaphore.acquire(timeout=timeout)
        if not ok:
            return None, TimeoutError(
                "Unable to acquire the lock before the timeout expiration"
            )

        if callable(getattr(self._inventory, "copy", None)):
            inventory_snapshot = self._inventory.copy()
        else:
            inventory_snapshot = copy(self._inventory)
        self._inv_semaphore.release()
        return inventory_snapshot

    def set_inventory(self, new_inventory, timeout: int = 10):
        """
        - Acquire semaphore
        - Update inventory
        - Release semaphore
        """
        self._inv_semaphore.acquire(timeout=timeout)
        if callable(getattr(self._inventory, "copy", None)):
            new_inventory_copy = new_inventory.copy()
        else:
            new_inventory_copy = copy(new_inventory)
        self._inventory = new_inventory_copy
        if not self._inv_is_set:
            # the inventory has been set for the first time
            self._inv_is_set = True
            self._inv_is_set_sem.release()
        self._inv_semaphore.release()

    def _get_loader_class(self, ltype):
        base_class_name = CredentialLoader.__name__
        module_path = abspath(dirname(getfile(CredentialLoader)))
        l_classes = get_class_by_path(
            module_path, module_path, base_class_name
        )

        if l_classes:
            return l_classes.get(ltype, None)
        return None
