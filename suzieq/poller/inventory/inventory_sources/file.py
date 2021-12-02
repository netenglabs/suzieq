"""
This module contains the logic of the plugin
in charge of importing an inventory from a
Suzieq inventory file.
"""
import logging
import os
from typing import Dict, List
from urllib.parse import urlparse

import yaml

from suzieq.poller.inventory.inventory_sources_base.inventory import Inventory
from suzieq.shared.exceptions import InventorySourceError

logger = logging.getLogger(__name__)


class SqNativeInventory(Inventory):
    """The SqNativeInventory is a class allowing to import
    a native Suzieq inventory file in the poller.
    """

    def __init__(self, add_task_fn, **kwargs) -> None:
        self.inventory_source = kwargs.pop('inventory', None)
        super().__init__(add_task_fn, **kwargs)

    def _get_hostsdata_from_hostsfile(self, hosts_file: str) -> Dict:
        """Read the suzieq devices file and return the data from the file
        and produce a dictionary containing its data.

        Args:
            hosts_file (str): the path where the file is located

        Raises:
            InventorySourceError: raised if the file is not valid.

        Returns:
            Dict: a dictionary containing the data in the inventory file
        """

        if not os.path.isfile(hosts_file):
            raise InventorySourceError(f'Suzieq inventory {hosts_file}'
                                       'must be a file')

        if not os.access(hosts_file, os.R_OK):
            raise InventorySourceError('Suzieq inventory file is '
                                       f'not readeable {hosts_file}')

        with open(hosts_file, 'r') as f:
            try:
                data = f.read()
                hostsconf = yaml.safe_load(data)
            except Exception as e:
                raise InventorySourceError('Invalid Suzieq inventory '
                                           f'file: {e}')

        if not hostsconf or isinstance(hostsconf, str):
            raise InventorySourceError('Invalid Suzieq inventory '
                                       f'file:{hosts_file}')

        if not isinstance(hostsconf, list):
            if '_meta' in hostsconf.keys():
                raise InventorySourceError('Invalid Suzieq inventory format, '
                                           'Ansible format?? Use -a instead '
                                           'of -D with inventory')
            else:
                raise InventorySourceError(
                    f'Invalid Suzieq inventory file:{hosts_file}')

        for conf in hostsconf:
            if any(x not in conf.keys() for x in ['namespace', 'hosts']):
                raise InventorySourceError(f'Invalid inventory:{hosts_file}, '
                                           'no namespace/hosts sections')

        return hostsconf

    def _get_device_list(self) -> List[Dict]:
        """Extract the data from the Suzieq inventory file
        and produce a List with the list of devices and their
        credentials

        Returns:
            List[Dict]: the list of the credentials of the devices
                in the Suzieq native inventory file.
        """
        inventory = []
        hostsconf = self._get_hostsdata_from_hostsfile(self.inventory_source)
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
                    except IndexError:
                        if 'password' not in words[i]:
                            logger.error(f"Missing '=' in key {words[i]}")
                        else:
                            logger.error("Invalid password spec., missing '='")
                        logger.error(f'Ignoring node {host}')
                        continue

                    inventory.append({
                        'address': host,
                        'username': username,
                        'port': port,
                        'password': password,
                        'transport': transport,
                        'devtype': devtype,
                        'namespace': nsname,
                        'ssh_keyfile': keyfile
                    })
                else:
                    logger.error(f'Ignoring invalid host spec.: {entry}')

        if not inventory:
            logger.error('No hosts detected in provided inventory file')
        return inventory
