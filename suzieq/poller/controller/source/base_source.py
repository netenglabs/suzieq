"""Module containing base class for inventorySource plugins
"""
import asyncio
from abc import abstractmethod
from copy import copy
from os.path import isfile
from pathlib import Path
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
        self._auth = input_data.get('auth')  # auth object
        self._device = input_data.get('device') or {}
        self._valid_fields = ['name', 'type', 'auth',
                              'device', 'namespace', 'run_once']

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

        self._validate_config(input_data)
        self._validate_device()

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

    def _validate_config(self, input_data: dict):
        """Checks if the loaded data is valid or not"""
        inv_fields = [x for x in input_data if x not in self._valid_fields]
        if inv_fields:
            raise InventorySourceError(
                f'{self._name}: unknown fields {inv_fields}')

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
        if self._auth:
            self._auth.load(new_inventory)
        self.set_device(new_inventory)
        missing_keys = self._is_invalid_inventory(new_inventory)
        if missing_keys:
            raise InventorySourceError(
                f'{self._name} missing informations: {missing_keys}')

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
        for host in inventory.values():
            host_keys = set(self._inv_format)
            for key in host.keys():
                if key in host_keys:
                    host_keys.remove(key)

            if host.get('transport') == 'https' and not host.get('devtype'):
                raise InventorySourceError('Missing devtype in https transport'
                                           f' for host {host.get("address")}')

            if host_keys:
                return list(host_keys)

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
            ptype = src_conf.get('type') or 'native'

            if ptype not in plugin_classes:
                raise RuntimeError(
                    f'Unknown plugin called {ptype}'
                )
            src_conf.update({'run_once': run_once})
            src_plugins.append(plugin_classes[ptype](src_conf))
        return src_plugins

    def set_device(self, inventory: Dict[str, Dict]):
        """Add device config from inventory file to the inventory

        Args:
            inventory (Dict[str,Dict]): inventory
        """
        jump_host = None
        jump_host_key_file = None
        transport = None
        ignore_known_hosts = None
        port = None
        devtype = None

        if self._device:
            jump_host = self._device.get('jump-host')
            if jump_host and not jump_host.startswith("//"):
                jump_host = f'//{jump_host}'
            jump_host_key_file = self._device.get('jump-host-key-file')
            if jump_host_key_file and \
                    not Path(jump_host_key_file).is_file():
                raise InventorySourceError(f'{self._name} Jump host key file'
                                           f" at {jump_host_key_file} doesn't"
                                           " exists")
            transport = self._device.get('transport')
            ignore_known_hosts = self._device.get('ignore-known-hosts', False)
            port = self._device.get('port')
            devtype = self._device.get('devtype')

        for node in inventory.values():
            node.update({
                'jump_host': node.get('jump_host') or jump_host,
                'jump_host_key_file': node.get('jump_host_key_file')
                or jump_host_key_file,
                'ignore_known_hosts': node.get('ignore_known_hosts')
                or ignore_known_hosts,
                'transport': node.get('transport') or transport or 'ssh',
                'port': node.get('port') or port or 22,
                'devtype': node.get('devtype') or devtype
            })

    def _validate_device(self):
        if self._device:
            dev_fields = ['name', 'jump-host', 'jump-host-key-file',
                          'ignore-known-hosts', 'transport', 'port', 'devtype']
            inv_fields = [x for x in self._device if x not in dev_fields]
            if inv_fields:
                raise InventorySourceError(
                    f'{self._device["name"]}: Unknow fields called '
                    f'{inv_fields}')


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

    sources_list = inventory.get('sources')

    sources = []
    for ns in ns_list:
        source = None
        namespace = ns.get('name')

        source_name = ns.get('source')

        source = sources_list.get(source_name)

        if ns.get('auth'):
            auth = inventory.get('auths', []).get(ns['auth'])
            auth_type = auth.get('type') or 'static'
            if "-" in auth_type:
                auth_type = auth_type.replace("-", "_")
            auth['type'] = auth_type
            source['auth'] = CredentialLoader.init_plugins(auth)[0]
        else:
            source['auth'] = None

        if ns.get('device'):
            device = inventory.get('devices', []).get(ns['device'])
            source['device'] = device
        else:
            source['device'] = None

        source['namespace'] = namespace

        sources.append(source)

    return sources
