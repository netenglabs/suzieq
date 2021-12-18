import logging
import re
from typing import Dict
from urllib.parse import urlparse
from ipaddress import ip_address

from suzieq.shared.utils import SUPPORTED_POLLER_TRANSPORTS
from suzieq.poller.controller.source.base_source import Source
from suzieq.shared.exceptions import InventorySourceError


logger = logging.getLogger(__name__)

_DEFAULT_PORTS = {'http': 80, 'https': 443, 'ssh': 22}


class SqNativeFile(Source):
    """Source class used to load Suzieq native inventory files
    """

    def __init__(self, input_data) -> None:
        self.inventory_source = ""
        self._cur_inventory = {}
        super().__init__(input_data)

    def _validate_config(self, input_data: dict):
        if any(x not in input_data.keys()
               for x in ['namespace', 'hosts']):
            raise InventorySourceError('Invalid file inventory: '
                                       'no namespace/hosts sections')
        if not isinstance(input_data.get("hosts"), list):
            raise InventorySourceError('Hosts must be a list')

    def _load(self, input_data):
        self.inventory_source = input_data
        self._cur_inventory = self._get_inventory()
        if self._auth:
            self._auth.load(self._cur_inventory)
        self.set_inventory(self._cur_inventory)

    def _get_inventory(self) -> Dict:
        """Extract the data from ansible inventory file

        Returns:
            Dict: inventory dictionary
        """
        inventory = {}

        nsname = self.inventory_source['namespace']

        hostlist = self.inventory_source.get('hosts', [])
        if not hostlist:
            logger.error(f'No hosts in namespace {nsname}')
            return []

        for address in hostlist:
            if not isinstance(address, dict):
                logger.error(f'Ignoring invalid host spec: {address}')
                continue
            entry = address.get('url', None)
            if entry:
                words = entry.split()
                decoded_url = urlparse(words[0])

                username = decoded_url.username
                password = (decoded_url.password or
                            # self.user_password or #I can't get this info here
                            None)
                transport = decoded_url.scheme or "http"
                port = decoded_url.port or _DEFAULT_PORTS.get(transport)
                address = decoded_url.hostname
                devtype = None
                keyfile = None

                try:
                    for i in range(1, len(words[1:])+1):
                        if words[i].startswith('keyfile'):
                            keyfile = words[i].split('=')[1]
                        elif words[i].startswith('devtype'):
                            devtype = words[i].split('=')[1]
                        elif words[i].startswith('username'):
                            username = words[i].split('=')[1]
                        elif words[i].startswith('password'):
                            password = words[i].split('=')[1]
                        else:
                            logger.error('Ignorning Unknown parameter: '
                                         f'{words[i]} for {address}')
                except IndexError:
                    if 'password' not in words[i]:
                        logger.error(f"Missing '=' in key {words[i]}")
                    else:
                        logger.error("Invalid password spec., missing '='")
                    logger.error(f'Ignoring node {address}')
                    continue

                entry = {
                    'address': address,
                    'username': username,
                    'port': port,
                    'password': password,
                    'transport': transport,
                    'devtype': devtype,
                    'namespace': nsname,
                    'ssh_keyfile': keyfile,
                    'hostname': None,
                    'jump_host': self._device.get('jump-host'),
                    'jump_host_key_file':
                    self._device.get('jump-host-key-file'),
                    'ignore_known_hosts':
                    self._device.get('ignore-known-hosts')
                }
                if self._validate_inventory_entry(entry):
                    # TODO: must add a credential_loader
                    inventory[f'{nsname}.{address}'] = entry
            else:
                logger.error(f'Ignoring invalid host spec.: {entry}')

        if not inventory:
            logger.error('No hosts detected in provided inventory file')

        return inventory

    def _validate_inventory_entry(self, entry: Dict) -> bool:
        """Validate the entry in the inventory file

        Args:
            entry (dict): the entry to validate

        Returns:
            bool: True if the entry is valid, False otherwise
        """
        if entry['transport'] not in SUPPORTED_POLLER_TRANSPORTS:
            logger.error(f'Transport {entry["transport"]} not supported for '
                         f'host {entry["address"]}')
            return False

        if entry['transport'] == 'https' and not entry['devtype']:
            logger.error('Missing devtype in https transport for '
                         f'host {entry["address"]}')
            return False

        if entry['devtype'] == "panos" and not entry['apiKey']:
            logger.error(f'Missing apiKey for panos host {entry["address"]}')
            return False

        if re.match(r'^[0-9a-f:.]', entry['address']):
            try:
                ip_address(entry['address'])
            except ValueError:
                logger.error(f'Invalid IP address {entry["address"]}'
                             f' for host {entry["address"]}')
                return False

        return True
