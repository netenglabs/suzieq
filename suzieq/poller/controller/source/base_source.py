"""Module containing base class for inventorySource plugins
"""
import asyncio
from copy import copy, deepcopy
from os.path import isfile
from pathlib import Path
from typing import Dict, List


from suzieq.poller.controller.base_controller_plugin import \
    ControllerPlugin, InventoryPluginModel
from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader, check_credentials
from suzieq.poller.controller.utils.inventory_utils import read_inventory
from suzieq.shared.exceptions import InventorySourceError

_DEFAULT_PORTS = {'http': 80, 'https': 443, 'ssh': 22}


class SourceModel(InventoryPluginModel):
    """Model for inventory source validation

    IMPORTANT:
    do not use namespace, device and auth as field names
    """


class Source(ControllerPlugin):
    """Base class for plugins which reads inventories"""

    def __init__(self, input_data, validate: bool = True) -> None:
        super().__init__(input_data, validate)

        self._inventory = {}
        self._inv_is_set = False
        self._inv_is_set_event = asyncio.Event()
        self._auth = input_data.pop('auth', None)  # auth object
        self._device = input_data.pop('device', {})
        self._namespace = input_data.pop('namespace')
        self._run_once = input_data.pop('run_once', False)
        self._data = None

        self._inv_format = [
            'address',
            'namespace',
            'port',
            'transport',
            'devtype',
            'hostname',
            'jump_host',
            'jump_host_key_file',
            'ignore_known_hosts',
            'slow_host',
            'per_cmd_auth',
        ]

        self._load(input_data)

    @property
    def name(self) -> str:
        """Name of the source set in the inventory file

        Returns:
            str: name of the source
        """
        return self._data.name

    @classmethod
    def default_type(cls) -> str:
        return 'native'

    @classmethod
    def get_data_model(cls):
        return SourceModel

    def _load(self, input_data):
        """Store informations from raw data"""
        if self._validate:
            self._data = self.get_data_model()(**input_data)
        else:
            self._data = self.get_data_model().construct(**input_data)
        if not self._data:
            raise InventorySourceError(
                'input_data was not loaded correctly')

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
        else:
            check_credentials(new_inventory)
        self.set_device(new_inventory)
        missing_keys = self._is_invalid_inventory(new_inventory)
        if missing_keys:
            raise InventorySourceError(
                f'{self.name} missing informations: {missing_keys}')

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
    def init_plugins(cls, plugin_conf: Dict, validate: bool = False)\
            -> List[Dict]:
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
        if not plugin_conf.get('path'):
            raise InventorySourceError('A source plugin cannot be initialized'
                                       'without the inventory file path')
        src_confs = _load_inventory(plugin_conf.get('path'))
        run_once = plugin_conf.get('single-run-mode', None)
        for src_conf in src_confs:
            ptype = src_conf.get('type') or Source.default_type()

            if ptype not in plugin_classes:
                raise RuntimeError(
                    f'Unknown plugin called {ptype}'
                )
            src_conf.update({'run_once': run_once})
            src_plugins.append(plugin_classes[ptype](
                deepcopy(src_conf), validate))
        return src_plugins

    def set_device(self, inventory: Dict[str, Dict]):
        """Add device config from inventory file to the inventory

        Args:
            inventory (Dict[str,Dict]): inventory
        """
        jump_host = None
        jump_host_key_file = None
        transport = None
        ignore_known_hosts = False
        slow_host = False
        per_cmd_auth = True
        retries_on_auth_fail = 0
        dev_port = None
        devtype = None

        if self._device:
            jump_host = self._device.get('jump-host')
            if jump_host and not jump_host.startswith("//"):
                jump_host = f'//{jump_host}'
            jump_host_key_file = self._device.get('jump-host-key-file')
            if jump_host_key_file and \
                    not Path(jump_host_key_file).is_file():
                raise InventorySourceError(f'{self.name} Jump host key file'
                                           f" at {jump_host_key_file} doesn't"
                                           " exists")
            transport = self._device.get('transport')
            if transport:
                # get the string from the enum
                transport = transport.value
            ignore_known_hosts = self._device.get('ignore-known-hosts', False)
            slow_host = self._device.get('slow-host', False)
            per_cmd_auth = self._device.get('per-cmd-auth', True)
            retries_on_auth_fail = self._device.get('retries-on-auth-fail', 0)
            dev_port = self._device.get('port')
            devtype = self._device.get('devtype')

        node_keys_to_remove = []
        nodes_to_add = {}
        for node_name, node in inventory.items():
            transport_tmp = node.get('transport') or transport or 'ssh'
            ignore_known_hosts_tmp = node.get('ignore_known_hosts')
            missing_node_port = not (node_port := node.get('port'))
            if missing_node_port:
                node_port = dev_port or _DEFAULT_PORTS.get(transport_tmp)
            node.update({
                'jump_host': node.get('jump_host') or jump_host,
                'jump_host_key_file': node.get('jump_host_key_file')
                or jump_host_key_file,
                'ignore_known_hosts': ignore_known_hosts_tmp if
                ignore_known_hosts_tmp is not None else ignore_known_hosts,
                'transport': transport_tmp,
                'port': node_port,
                'devtype': node.get('devtype') or devtype,
                'slow_host': node.get('slow_host', '') or slow_host,
                'per_cmd_auth': ((node.get('per_cmd_auth', '') != '')
                                 or per_cmd_auth),
                'retries_on_auth_fail': ((node.get('retries_on_auth_fail',
                                                   -1) != -1) or
                                         retries_on_auth_fail)
            })
            if missing_node_port:
                # An inventory key is composed by
                # '{namespace}.{address}.{port}'. If the node port is missing,
                # the key generated is not complete.
                # We need to assign the node to a correct key. Since we are
                # looping on the items in the inventory, we cannot update it
                # here. We need to do it after the loop is completed, so we are
                # storing in "node_keys_to_remove" the invalid key and in
                # "nodes_to_add" the current node assigned to the correct key
                node_keys_to_remove.append(node_name)
                new_key = f"{node['namespace']}.{node['address']}.{node_port}"
                nodes_to_add[new_key] = node

        if node_keys_to_remove:
            for k in node_keys_to_remove:
                del inventory[k]

        if nodes_to_add:
            inventory.update(nodes_to_add)

    def _validate_device(self):
        if self._device:
            dev_fields = ['name', 'jump-host', 'jump-host-key-file',
                          'ignore-known-hosts', 'transport', 'port',
                          'slow-host', 'per_cmd_auth', 'retries_on_auth_fail',
                          'devtype']
            inv_fields = [x for x in self._device if x not in dev_fields]
            if inv_fields:
                raise InventorySourceError(
                    f'{self._device.get("name")}: Unknown fields called '
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
    sources_dict = inventory.get('sources')
    auths_dict = inventory.get('auths', {})
    devs_dict = inventory.get('devices', {})

    sources = []
    for ns in ns_list:
        source_name = ns.get('source')
        namespace = ns.get('name')

        source = sources_dict.get(source_name)

        if ns.get('auth'):
            # this is only a temporary fix, in future releases I will move the
            # credential loader initialization outside of this function.
            auth = deepcopy(auths_dict.get(ns['auth']))
            auth_type = auth.get('type') or CredentialLoader.default_type()
            if "-" in auth_type:
                auth_type = auth_type.replace("-", "_")
            auth['type'] = auth_type
            source['auth'] = CredentialLoader.init_plugins(auth)[0]
        else:
            source['auth'] = None

        if ns.get('device'):
            device = devs_dict.get(ns['device'])
            source['device'] = device
        else:
            source['device'] = None

        source['namespace'] = namespace

        sources.append(source)

    return sources
