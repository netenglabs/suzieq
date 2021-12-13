"""
This module contains the logic of the plugin
in charge of importing an inventory from a
Suzieq inventory file.
"""
import logging
import re
from typing import Dict, List
from urllib.parse import urlparse
from ipaddress import ip_address

from suzieq.poller.inventory.inventory_sources_base.inventory import Inventory
from suzieq.shared.inventories_parsing import get_hostsdata_from_hostsfile
from suzieq.shared.utils import SUPPORTED_POLLER_TRANSPORTS

logger = logging.getLogger(__name__)


class SqNativeInventory(Inventory):
    """The SqNativeInventory is a class allowing to import
    a native Suzieq inventory file in the poller.
    """

    def __init__(self, add_task_fn, **kwargs) -> None:
        self.inventory_source = kwargs.pop('inventory', None)
        super().__init__(add_task_fn, **kwargs)

    def _get_device_list(self) -> List[Dict]:
        """Extract the data from the Suzieq inventory file

        Returns:
            List[Dict]: list with the data to connect to the devices in the
                inventory
        """
        inventory = []
        hostsconf = get_hostsdata_from_hostsfile(self.inventory_source)
        for namespace in hostsconf:
            nsname = namespace['namespace']

            hostlist = namespace.get('hosts', [])
            if not hostlist:
                logger.error(f'No hosts in namespace {nsname}')
                continue

            for host in hostlist:
                if not isinstance(host, dict):
                    logger.error(f'Ignoring invalid host spec: {host}')
                    continue
                entry = host.get('url', None)
                if entry:
                    words = entry.split()
                    decoded_url = urlparse(words[0])

                    username = decoded_url.username
                    password = (decoded_url.password or
                                self.user_password or
                                'vagrant')
                    port = decoded_url.port
                    host = decoded_url.hostname
                    transport = decoded_url.scheme
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
                                             f'{words[i]} for {host}')
                    except IndexError:
                        if 'password' not in words[i]:
                            logger.error(f"Missing '=' in key {words[i]}")
                        else:
                            logger.error("Invalid password spec., missing '='")
                        logger.error(f'Ignoring node {host}')
                        continue

                    entry = {
                        'address': host,
                        'username': username,
                        'port': port,
                        'password': password,
                        'transport': transport,
                        'devtype': devtype,
                        'namespace': nsname,
                        'ssh_keyfile': keyfile
                    }
                    if self._validate_inventory_entry(entry):
                        inventory.append(entry)
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

        if re.match(r'^[0-9a-f:.]', entry['address']):
            try:
                ip_address(entry['address'])
            except ValueError:
                logger.error(f'Invalid IP address {entry["address"]}'
                             f' for host {entry["address"]}')
                return False

        return True
