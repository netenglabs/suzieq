"""
This module contains the logic of the plugin in charge of importing an
inventory from an Ansible inventory file.
"""
from pathlib import Path
from typing import Dict
import logging
import yaml
from suzieq.poller.controller.source.base_source import Source
from suzieq.shared.exceptions import InventorySourceError

logger = logging.getLogger(__name__)


class AnsibleInventory(Source):
    """The AnsibleInventory is a class allowing to import the output
    of 'ansible-inventory command' as input of the poller.
    """

    def __init__(self, input_data: dict) -> None:
        self.ansible_file = ''
        self.namespace = ''
        super().__init__(input_data)

    def _load(self, input_data):
        self.ansible_file = input_data.get('path', None)
        self.namespace = input_data.get('namespace', None)
        inventory = self._get_inventory()
        self.set_inventory(inventory)

    def _validate_config(self, input_data: dict):
        self._valid_fields.extend(['path'])
        super()._validate_config(input_data)

        if not input_data.get('path'):
            raise InventorySourceError(
                f"{self._name} 'path' field must be specified"
            )

        if not Path(input_data['path']).is_file():
            raise InventorySourceError(
                f"{self._name} No file found at {input_data['path']}")

    def _get_inventory(self) -> Dict:
        """Parse the output of ansible-inventory command for processing.

        Ansible pulls together the inventory information from multiple files.
        The information relevant to sq-poller maybe present in different files
        as different vars. ansible-inventory command luckily handles this for
        us. This function takes the JSON output of that command and gathers
        the data needed to start polling.

        Raises:
            InventorySourceError: raised if the file is not valid or cannot
                be read.

        Returns:
            Dict: A list containing a dictionary of data with the data to
                connect to the host.
        """
        try:
            with open(self.ansible_file, 'r') as f:
                inventory = yaml.safe_load(f)
        except Exception as error:
            raise InventorySourceError(
                f'Unable to process Ansible inventory: {str(error)}'
            )

        if '_meta' not in inventory or 'hostvars' not in inventory['_meta']:
            if isinstance(inventory, list) and 'namespace' in inventory[0]:
                raise InventorySourceError(
                    'Invalid Ansible inventory, found Suzieq inventory'
                )
            raise InventorySourceError(
                'Invalid Ansible inventory, missing keys: _meta and / or'
                "hostvars\n \tUse 'ansible-inventory --list' to create "
                'the correct file'
            )

        in_hosts = inventory['_meta']['hostvars']
        out_inv = {}
        for host in in_hosts:
            entry = in_hosts[host]

            ansible_host = entry.get('ansible_host')
            if not ansible_host:
                logger.warning(f'{self._name} skipping ansible device '
                               'without hostname')
                continue

            ansible_user = entry.get('ansible_user')
            if not ansible_user:
                logger.warning(
                    f'{self._name} skipping ansible device without username')
                continue

            # Get password if any
            password = None
            if 'ansible_password' in entry:
                password = entry['ansible_password']

            # Retrieve password information
            devtype = None
            if entry.get('ansible_network_os') in ['eos', 'panos']:
                devtype = entry.get('ansible_network_os')
                transport = 'https'
                port = 443
            else:
                transport = 'ssh'
                port = entry.get('ansible_port', 22)

            # Get keyfile
            keyfile = entry.get('ansible_ssh_private_key_file', None)
            if keyfile and not Path(keyfile).exists():
                logger.warning(
                    f"{self._name} Ignored host {ansible_host} because "
                    f"associated keyfile {keyfile} does not exist"
                )
                continue

            host = {
                'address': ansible_host,
                'username': ansible_user,
                'port': port,
                'password': password,
                'transport': transport,
                'devtype': devtype,
                'namespace': self.namespace,
                'ssh_keyfile': keyfile,
                'hostname': None
            }
            out_inv[f"{self.namespace}.{ansible_host}.{port}"] = host

        return out_inv
