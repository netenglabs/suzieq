import logging
import re
from typing import Dict
from urllib.parse import urlparse
from ipaddress import ip_address
from pathlib import Path

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
        self._valid_fields.extend(['hosts'])
        super()._validate_config(input_data)

        if not input_data.get('hosts'):
            raise InventorySourceError(f"{self._name} The 'hosts' field with "
                                       "the list of nodes to poll is mandatory"
                                       )

        if not isinstance(input_data.get('hosts'), list):
            raise InventorySourceError(f"{self._name} 'hosts' field must be a "
                                       "list")

    def _load(self, input_data):
        self.inventory_source = input_data
        self._cur_inventory = self._get_inventory()
        self.set_inventory(self._cur_inventory)

    def _get_inventory(self) -> Dict:
        """Extract the data from ansible inventory file

        Returns:
            Dict: inventory dictionary
        """
        inventory = {}

        nsname = self.inventory_source['namespace']

        hostlist = self.inventory_source.get('hosts', [])

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

                if keyfile and not Path(keyfile).exists():
                    logger.warning(
                        f"Ignored host {address} not existing "
                        f'keyfile: {keyfile}'
                    )
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
                }
                self._validate_inventory_entry(entry)
                inventory[f'{nsname}.{address}.{port}'] = entry
            else:
                logger.error(f'Ignoring invalid host spec.: {entry}')

        if not inventory:
            logger.error('No hosts detected in provided inventory file')

        return inventory

    def _validate_inventory_entry(self, entry: Dict):
        """Validate the entry in the inventory file

        Args:
            entry (dict): the entry to validate

        Returns:
            bool: True if the entry is valid, False otherwise
        """
        if entry['transport'] not in SUPPORTED_POLLER_TRANSPORTS:
            raise InventorySourceError(f'Transport {entry["transport"]} not '
                                       f'supported for host {entry["address"]}'
                                       )

        # if entry['transport'] == 'https' and not entry['devtype']:
        #     raise InventorySourceError('Missing devtype in https transport'
        #                                f' for host {entry["address"]}')

        # if entry['devtype'] == "panos" and not entry['apiKey']:
        #     raise InventorySourceError(
        #         f'Missing apiKey for panos host {entry["address"]}')

        if re.match(r'^[0-9a-f:.]', entry['address']):
            try:
                ip_address(entry['address'])
            except ValueError:
                raise InventorySourceError('Invalid IP address'
                                           f'{entry["address"]} for host '
                                           f'{entry["address"]}')
