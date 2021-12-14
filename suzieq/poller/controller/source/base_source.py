"""Module containing base class for inventorySource plugins
"""
from abc import abstractmethod
from copy import copy
from threading import Semaphore
from typing import Dict, List
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
    def init_plugins(cls, plugin_conf: dict) -> List[Dict]:
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
            raise InventorySourceError(
                "Parameter 'path' is mandatory for source")
        src_confs = _load_inventory(plugin_conf["path"])
        for src_conf in src_confs:
            ptype = src_conf.get("type") or "file"

            if ptype not in plugin_classes:
                raise RuntimeError(
                    f"Unknown plugin called {ptype}"
                )
            src_plugins.append(plugin_classes[ptype](src_conf))
        return src_plugins


def _load_inventory(source_path: str) -> List[dict]:
    """Load inventory from a file

    Args:
        source_path (str): inventory file

    Raises:
        InventorySourceError: inventory file doesn't exists
        or invalid

    Returns:
        List[dict]: list of sources
    """
    if not isfile(source_path):
        raise InventorySourceError(f"File {source_path} doesn't exists")

    inventory = {
        "sources": {},
        "devices": {},
        "auths": {}
    }

    inventory_data = {}
    with open(source_path, "r") as fp:
        file_content = fp.read()
        try:
            inventory_data = yaml.safe_load(file_content)
        except Exception as e:
            raise InventorySourceError('Invalid Suzieq inventory '
                                       f'file: {e}')
    _validate_raw_inventory(inventory_data)

    for k in inventory:
        inventory[k] = _get_inventory_config(k, inventory_data)

    ns_list = inventory_data.get("namespaces")

    sources = []
    for ns in ns_list:
        source = None
        namespace = ns.get("namespace")

        source_name = ns.get("source")

        source = inventory.get("sources").get(source_name)

        if ns.get("auth"):
            auth = inventory.get("auths", {}).get(ns["auth"])
            source["auth"] = CredentialLoader.init_plugins(auth)[0]
        else:
            source["auth"] = None

        if ns.get("device"):
            device = inventory.get("devices", {}).get(ns["device"])
            source["device"] = device
        else:
            source["device"] = None

        source["namespace"] = namespace

        sources.append(source)

    return sources


def _validate_raw_inventory(inventory: dict):
    """Validate the inventory read from file

    Args:
        inventory (dict): inventory read from file

    Raises:
        InventorySourceError: invalid inventory
    """
    if not inventory:
        raise InventorySourceError('The inventory is empty')

    for f in ["sources", "namespaces"]:
        if f not in inventory:
            raise InventorySourceError(
                "'sources' and 'namespaces' fields must be specified")

    main_fields = {
        "sources": [],
        "devices": [],
        "auths": [],
    }
    for mf in main_fields:
        fields = inventory.get(mf)
        if not fields:
            # 'devices' and 'auths' can be omitted if not needed
            continue
        if not isinstance(fields, list):
            raise InventorySourceError(f"{mf} content must be a list")
        for value in fields:
            name = value.get("name")
            if not name:
                raise InventorySourceError(
                    f"{mf} items must have a 'name'")
            if name in main_fields[mf]:
                raise InventorySourceError(f"{mf}.{name} is not unique")
            main_fields[mf].append(name)

            if not isinstance(value, dict):
                raise InventorySourceError(
                    f"{mf}.{name} is not a dictionary")

            if value.get("copy") and not value["copy"] in main_fields[mf]:
                raise InventorySourceError(f"{mf}.{name} value must be a "
                                           "'name' of an already defined "
                                           f"{mf} item")
    # validate 'namespaces'
    for ns in inventory.get("namespaces"):
        if not ns.get("source"):
            raise InventorySourceError(
                "all namespaces need 'source' field")

        if ns.get("source") not in main_fields["sources"]:
            raise InventorySourceError(
                    f"No source called '{ns['source']}'")

        if ns.get("device") and ns['device'] not in main_fields["devices"]:
            raise InventorySourceError(
                    f"No device called '{ns['device']}'")

        if ns.get("auth") and ns['auth'] not in main_fields["auths"]:
            raise InventorySourceError(
                    f"No auth called '{ns['auth']}'")


def _get_inventory_config(conf_type: str, inventory: dict) -> dict:
    """Return the configuration for a the config type as input

    The returned value will contain a dictionary with 'name' as key
    and the config as value

    Args:
        conf_type (str): type of configuration to initialize
        inventory (dict): inventory to read to collect configuration

    Returns:
        dict: configuration data
    """
    configs = {}
    conf_list = inventory.get(conf_type)
    if not conf_list:
        # No configuration specified
        return {}

    for conf_obj in conf_list:
        name = conf_obj.get("name")
        if name:
            if conf_obj.get("copy"):
                # copy the content of the other inventory
                # into the current inventory and override
                # values
                configs[name] = configs[conf_obj["copy"]].copy()
                for k, v in conf_obj.items():
                    if k not in ["copy"]:
                        configs[name][k] = v
            else:
                configs[name] = conf_obj

    return configs
