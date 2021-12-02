"""
This module contains all the shared logic for the inventory sources parsing
"""
import logging
import os
from os.path import exists
from typing import Dict, List

import yaml

from suzieq.shared.exceptions import InventorySourceError

logger = logging.getLogger(__name__)


def get_hostsdata_from_hostsfile(hosts_file: str) -> Dict:
    """Read the suzieq devices file and return the data from the file
    and produce a dictionary containing its content.

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


def parse_ansible_inventory(filename: str,
                            namespace: str = 'default') -> List[Dict]:
    """Parse the output of ansible-inventory command for processing.

    Ansible pulls together the inventory information from multiple files. The
    information relevant to sq-poller maybe present in different files as
    different vars. ansible-inventory command luckily handles this for us. This
    function takes the JSON output of that command and gathers the data needed
    to start polling.

    Args:
        filename (str): file containing the output of ansible-inventory output
        namespace (str, optional): The namespace to assign to the nodes in the
        ansible file. Defaults to 'default'.

    Raises:
        InventorySourceError: raised if the file is not valid or cannot
            be read.

    Returns:
        List[Dict]: A list containing a dictionary of data with the data to
            connect to the host.
    """
    try:
        with open(filename, 'r') as f:
            inventory = yaml.safe_load(f)
    except Exception as error:
        raise InventorySourceError(
            f'Unable to process Ansible inventory: {str(error)}'
        )

    if '_meta' not in inventory or "hostvars" not in inventory['_meta']:
        if isinstance(inventory, list) and 'namespace' in inventory[0]:
            raise InventorySourceError(
                'Invalid Ansible inventory, found Suzieq inventory'
            )
        else:
            raise InventorySourceError(
                'Invalid Ansible inventory, missing keys: _meta and / or'
                "hostvars\n \tUse 'ansible-inventory --list' to create "
                'the correct file'
            )

    in_hosts = inventory['_meta']['hostvars']
    out_hosts = []
    for host in in_hosts:
        entry = in_hosts[host]

        # Get password if any
        password = ''
        if 'ansible_password' in entry:
            password = entry["ansible_password"]

        # Retrieve password information
        devtype = None
        if entry.get('ansible_network_os', '') == 'eos':
            transport = 'https'
            devtype = 'eos'
            port = 443
        else:
            transport = 'ssh'
            port = entry.get("ansible_port", 22)

        # Get keyfile
        keyfile = entry.get('ansible_ssh_private_key_file', '')
        if keyfile and not exists(keyfile):
            logger.warning(
                f"Ignored host {entry['ansible_host']} not existing "
                f'keyfile: {keyfile}'
            )
            continue

        host = {
            'address': entry['ansible_host'],
            'username': entry['ansible_user'],
            'port': port,
            'password': password,
            'transport': transport,
            'devtype': devtype,
            'namespace': namespace,
            'ssh_keyfile': keyfile
        }
        out_hosts.append(host)

    return out_hosts
