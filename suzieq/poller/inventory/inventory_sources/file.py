import logging
import os
from urllib.parse import urlparse

import yaml

from suzieq.poller.inventory.inventory_sources_base.inventory import Inventory

logger = logging.getLogger(__name__)


class sqNativeInventory(Inventory):

    def __init__(self, add_task_fn, **kwargs) -> None:
        self.inventory_source = kwargs.pop('inventory', None)
        super().__init__(add_task_fn, **kwargs)

    def _get_hostsdata_from_hostsfile(self, hosts_file) -> dict:
        """Read the suzieq devices file and return the data from the file"""

        if not os.path.isfile(hosts_file):
            raise AttributeError(f'Suzieq inventory {hosts_file}'
                                 'must be a file')

        if not os.access(hosts_file, os.R_OK):
            raise AttributeError('Suzieq inventory file is '
                                 f'not readeable {hosts_file}')

        with open(hosts_file, 'r') as f:
            try:
                data = f.read()
                hostsconf = yaml.safe_load(data)
            except Exception as e:
                raise AttributeError(f'Invalid Suzieq inventory file: {e}')

        if not hostsconf or isinstance(hostsconf, str):
            raise AttributeError(f'Invalid Suzieq inventory file:{hosts_file}')

        if not isinstance(hostsconf, list):
            if '_meta' in hostsconf.keys():
                raise AttributeError('Invalid Suzieq inventory format, '
                                     'Ansible format?? Use -a instead '
                                     'of -D with inventory')
            else:
                raise AttributeError(
                    f'Invalid Suzieq inventory file:{hosts_file}')

        for conf in hostsconf:
            if any(x not in conf.keys() for x in ['namespace', 'hosts']):
                raise AttributeError(f'Invalid inventory:{hosts_file}, '
                                     'no namespace/hosts sections')

        return hostsconf

    def _get_device_list(self):
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
                        'nsname': nsname,
                        'keyfile': keyfile
                    })
                else:
                    logger.error(f'Ignoring invalid host spec.: {entry}')

        if not inventory:
            logger.error('No hosts detected in provided inventory file')
        return inventory
