"""Module containing base class for inventorySource plugins
"""
import asyncio
from abc import abstractmethod
from copy import copy
from os.path import isfile
from typing import Dict, List

from suzieq.poller.controller.base_controller_plugin import ControllerPlugin
from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader
from suzieq.poller.controller.utils.inventory_utils import read_inventory
from suzieq.shared.exceptions import InventorySourceError

_DEFAULT_SOURCE_PATH = 'suzieq/.poller/intentory/inventory.yaml'


class Source(ControllerPlugin):
    """Base class for plugins which reads inventories"""

    def __init__(self, input_data) -> None:
        super().__init__()

        self._inventory = {}
        self._inv_is_set = False
        self._inv_is_set_event = asyncio.Event()
        self._name = input_data.get('name')
        self._auth = input_data.get('auth')
        self._device = input_data.get('device') or {}

        self._inv_format = [
            'address',
            'namespace',
            'port',
            'transport',
            'devtype',
            'hostname',
            'jump_host',
            'jump_host_key_file',
            'ignore_known_hosts'
        ]
        errors = self._validate_config(input_data)
        if errors:
            raise InventorySourceError('Inventory validation failed: {}'
                                       .format(errors))
        self._load(input_data)

    @property
    def name(self) -> str:
        """Name of the source set in the inventory file

        Returns:
            str: name of the source
        """
        return self._name

    @abstractmethod
    def _load(self, input_data):
        """Store informations from raw data"""
        raise NotImplementedError

    @abstractmethod
    def _validate_config(self, input_data: dict):
        """Checks if the loaded data is valid or not"""
        raise NotImplementedError

    async def get_inventory(self) -> Dict:
        """Retrieve the inventory from the source. If the inventory is not
        ready the function will wait until it is.

        Returns:
            List[Dict]: the device inventory from the source
        """
        # If the inventory is not ready wait until it is
        if not self._inv_is_set:
            await self._inv_is_set_event.wait()

        inventory_snapshot = copy(self._inventory)

        return inventory_snapshot

    def set_inventory(self, new_inventory: Dict):
        """Set the inventory in a thread safe way

        The function will try to set the inventory until the timeout
        expires.

        Before setting the new inventory, it calls the validator.

        Args:
            new_inventory ([List[Dict]]): the new inventory to set
        """

        self._inventory = new_inventory

        # If the inventory has been set for the first time, we need to
        # unlock who is waiting for it
        if not self._inv_is_set:
            # the inventory has been set for the first time
            self._inv_is_set = True
            self._inv_is_set_event.set()

    def _is_invalid_inventory(self, inventory: Dict) -> List[str]:
        """Validate the inventory

        The goal of this function is to check that all the devices has all
        the values in self._inv_format

        This function is called inside the set_inventory

        Args:
            inventory (Dict): inventory to validate

        Returns:
            List[str]: list of missing fields
        """
        for device in inventory.values():
            device_keys = set(self._inv_format)
            for key in device.keys():
                if key in device_keys:
                    device_keys.remove(key)

            if 'password' in device_keys and 'ssh_keyfile' in device_keys:
                device_keys.remove('password')
                device_keys.remove('ssh_keyfile')
                ret = list(device_keys)
                ret.append('password or ssh_keyfile')
                return ret

            if 'password' in device_keys:
                device_keys.remove('password')

            if 'ssh_keyfile' in device_keys:
                device_keys.remove('ssh_keyfile')

            if device_keys:
                return list(device_keys)

        return []

    @classmethod
    def init_plugins(cls, plugin_conf: Dict) -> List[Dict]:
        """This method is overrided because sources is different from other
        plugins.
        From the fields 'path', this function is going to load more than
        one source.
        The generate function for all other plugin will simply read the
        configuration and instance an object

        Args:
            plugin_conf (Dict): source plugin configuration dictionary.
            Must contain 'path' key with the inventory file as value.

        Raises:
            InventorySourceError: No 'path' key in plugin_conf
            RuntimeError: Unknown plugin

        Returns:
            List[Dict]: [description]
        """
        src_plugins = []
        plugin_classes = cls.get_plugins()
        src_confs = _load_inventory(
            plugin_conf.get('path', _DEFAULT_SOURCE_PATH))
        run_once = plugin_conf.get('run-once', False)
        for src_conf in src_confs:
            ptype = src_conf.get('type') or 'file'

            if ptype not in plugin_classes:
                raise RuntimeError(
                    f'Unknown plugin called {ptype}'
                )
            src_conf.update({'run_once': run_once})
            src_plugins.append(plugin_classes[ptype](src_conf))
        return src_plugins


def _load_inventory(source_file: str) -> List[dict]:
    """Load inventory from a file

    Args:
        source_file (str): inventory file

    Raises:
        InventorySourceError: inventory file doesn't exists
        or invalid

    Returns:
        List[dict]: list of sources
    """
    if not isfile(source_file):
        raise InventorySourceError(f"File {source_file} doesn't exists")

    inventory = read_inventory(source_file)

    ns_list = inventory.get('namespaces')

    sources = []
    for ns in ns_list:
        source = None
        namespace = ns.get('namespace')

        source_name = ns.get('source')

        source = inventory.get('sources').get(source_name)

        if ns.get('auth'):
            auth = inventory.get('auths', {}).get(ns['auth'])
            auth['type'] = auth.get('type') or 'static_loader'
            source['auth'] = CredentialLoader.init_plugins(auth)[0]
        else:
            source['auth'] = None

        if ns.get('device'):
            device = inventory.get('devices', {}).get(ns['device'])
            source['device'] = device
        else:
            source['device'] = None

        source['namespace'] = namespace

        sources.append(source)

    return sources
