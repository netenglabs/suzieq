"""
This module contains the logic of the plugin in charge of importing an
inventory from an Ansible inventory file.
"""
import yaml
import logging
from os.path import isfile, exists
from typing import Dict, List
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
        self.ansible_file = input_data.pop('file_path', None)
        self.namespace = input_data.pop('namespace', None)
        inventory = self._get_device_list()
        self.set_inventory(inventory)

    def _validate_config(self, input_data: dict):
        if any(x not in input_data.keys()
               for x in ['namespace', 'file_path']):
            raise InventorySourceError('Invalid file inventory: '
                                       'no namespace/file_path sections')

        if not isfile(input_data['file_path']):
            raise InventorySourceError(
                f"No file found at {input_data['file_path']}")

    def _get_device_list(self) -> List[Dict]:
        """Parse the output of ansible-inventory command for processing.

        Ansible pulls together the inventory information from multiple files. The
        information relevant to sq-poller maybe present in different files as
        different vars. ansible-inventory command luckily handles this for us. This
        function takes the JSON output of that command and gathers the data needed
        to start polling.

        Raises:
            InventorySourceError: raised if the file is not valid or cannot
                be read.

        Returns:
            List[Dict]: A list containing a dictionary of data with the data to
                connect to the host.
        """
        try:
            with open(self.ansible_file, 'r') as f:
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
        for i, host in enumerate(in_hosts):
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
                'namespace': self.namespace,
                'ssh_keyfile': keyfile,
                'id': str(i)
            }
            out_hosts.append(host)

        return out_hosts
