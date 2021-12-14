"""Module containing base class for inventorySource plugins
"""
from abc import abstractmethod
from copy import copy
from threading import Semaphore
from typing import Dict, Type, List
from os.path import isfile
import yaml
from suzieq.poller.controller.credential_loader.base_credential_loader \
    import CredentialLoader
from suzieq.shared.exceptions import InventorySourceError
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin


class Source(ControllerPlugin):
    """Base class for plugins which reads inventories"""

    def __init__(self, input_data) -> None:
        super().__init__()

        self._inv_semaphore = Semaphore()
        self._inventory = []
        self._inv_is_set = False
        self._inv_is_set_sem = Semaphore()
        self._inv_is_set_sem.acquire()

        self._inv_format = [
            "id",
            "address",
            "namespace",
            "port",
            "transport",
            "username",
            "password",
            "ssh_keyfile",
            "devtype"
        ]
        errors = self._validate_config(input_data)
        if errors:
            raise InventorySourceError("Inventory validation failed: {}"
                                       .format(errors))
        self._load(input_data)

    @abstractmethod
    def _load(self, input_data):
        """Store informations from raw data"""
        raise NotImplementedError

    @abstractmethod
    def _validate_config(self, input_data: dict):
        """Checks if the loaded data is valid or not"""
        raise NotImplementedError

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

        Args:
            new_inventory ([List[Dict]]): new inventory to set
            timeout (int, optional): maximum amount of time to wait.
            Defaults to 10.

        Raises:
            ValueError: invalid inventory file
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
        cred_loader_pkg = "suzieq.poller.controller.credential_loader"
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

            if "password" in device_keys and "ssh_keyfile" in device_keys:
                device_keys.remove("password")
                device_keys.remove("ssh_keyfile")
                ret = list(device_keys)
                ret.append("password or ssh_keyfile")
                return ret

            if "password" in device_keys:
                device_keys.remove("password")

            if "ssh_keyfile" in device_keys:
                device_keys.remove("ssh_keyfile")

            if device_keys:
                return list(device_keys)

        return []

    @classmethod
    def generate(cls, plugin_conf: dict) -> List[Dict]:
        """This method is overrided because sources is different from other
        plugins.
        From the fields 'path', this function is going to load more than
        one source.
        The generate function for all other plugin will simply read the
        configuration and instance an object

        Args:
            plugin_conf (dict): source plugin configuration dictionary.
            Must contain 'path' key with the inventory file as value.

        Raises:
            InventorySourceError: No 'path' key in plugin_conf
            RuntimeError: Unknown plugin

        Returns:
            List[Dict]: [description]
        """
        src_plugins = []
        plugin_classes = cls.get_plugins()
        if not plugin_conf.get("path"):
            raise InventorySourceError("No file provided for source")
        src_confs = _load_plugins_from_path(plugin_conf["path"])
        for src_conf in src_confs:
            ptype = src_conf.get("type") or "file"

            if ptype not in plugin_classes:
                raise RuntimeError(
                    f"Unknown plugin called {ptype}"
                )
            src_plugins.append(plugin_classes[ptype](src_conf))
        return src_plugins


def _load_plugins_from_path(source_path: str) -> Type:
    """Load the plugin from another file

    Args:
        source_path (str): file which contains plugin configuration

    Raises:
        RuntimeError: file doesn't exists

    Returns:
        [Type]: plugin configuration
    """
    # TODO: right now the only supported format is yaml.
    # We need to find a way to import also json

    if not isfile(source_path):
        raise RuntimeError(f"File {source_path} doesn't exists")

    plugins_data = []
    with open(source_path, "r") as fp:
        file_content = fp.read()
        try:
            plugins_data = yaml.safe_load(file_content)
        except Exception as e:
            raise InventorySourceError('Invalid Suzieq inventory '
                                       f'file: {e}')

    return plugins_data
