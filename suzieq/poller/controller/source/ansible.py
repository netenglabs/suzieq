"""
This module contains the logic of the plugin in charge of importing an
inventory from an Ansible inventory file.
"""
# pylint: disable=no-self-argument

from pathlib import Path
from typing import Dict, Union
import logging
from pydantic import Field, validator
import yaml
from suzieq.poller.controller.source.base_source import Source, SourceModel

logger = logging.getLogger(__name__)


class AnsibleSourceModel(SourceModel):
    """Model used to validate ansible input format
    """
    hosts: Union[str, Dict] = Field(alias='path')

    @validator('hosts')
    def validate_and_set(cls, path: str):
        """checks if the path is valid
        """
        if isinstance(path, str):
            if not Path(path).is_file():
                raise ValueError(
                    f"No file found at {path}")

            try:
                with open(path, 'r') as f:
                    inventory = yaml.safe_load(f)
            except Exception as error:
                raise ValueError(
                    f'Unable to process Ansible inventory: {str(error)}'
                )

        elif isinstance(path, Dict):
            inventory = path
        if '_meta' not in inventory \
                or 'hostvars' not in inventory['_meta']:
            if isinstance(inventory, list) and 'namespace' in inventory[0]:
                raise ValueError(
                    'Invalid Ansible inventory, found Suzieq inventory'
                )
            raise ValueError(
                'Invalid Ansible inventory, missing keys: _meta and / or'
                "hostvars\n \tUse 'ansible-inventory --list' to create "
                'the correct file'
            )

        return inventory['_meta']['hostvars']


class AnsibleInventory(Source):
    """The AnsibleInventory is a class allowing to import the output
    of 'ansible-inventory command' as input of the poller.
    """

    @classmethod
    def get_data_model(cls):
        return AnsibleSourceModel

    def _load(self, input_data):
        # pydantic aliases mess up things
        # put back data in 'hosts' from the 'path' alias
        if not self._validate:
            input_data['hosts'] = input_data.pop('path', {})

        super()._load(input_data)
        inventory = self._get_inventory()
        self.set_inventory(inventory)

    def _get_inventory(self) -> Dict:
        """Parse the output of ansible-inventory command for processing.

        Ansible pulls together the inventory information from multiple files.
        The information relevant to sq-poller maybe present in different files
        as different vars. ansible-inventory command luckily handles this for
        us. This function takes the JSON output of that command and gathers
        the data needed to start polling.

        Returns:
            Dict: A list containing a dictionary of data with the data to
                connect to the host.
        """

        in_hosts = self._data.hosts
        out_inv = {}
        for host in in_hosts:
            entry = in_hosts[host]

            ansible_host = entry.get('ansible_host')
            if not ansible_host:
                logger.warning(f'{self.name} skipping ansible device '
                               'without hostname')
                continue

            ansible_user = entry.get('ansible_user')
            if not ansible_user:
                logger.warning(
                    f'{self.name} skipping ansible device without username')
                continue

            # Get password if any
            password = None
            if 'ansible_password' in entry:
                password = entry['ansible_password']

            if 'ansible_ssh_pass' in entry:
                password = entry['ansible_ssh_pass']

            devtype = None
            if entry.get('ansible_network_os') in ['panos']:
                devtype = 'panos'
                transport = 'https'
                port = 443
            else:
                port = entry.get('ansible_port', 22)
                if port == 443:
                    transport = 'https'
                else:
                    transport = 'ssh'

            # Get keyfile
            keyfile = entry.get('ansible_ssh_private_key_file', None)
            if keyfile and not Path(keyfile).exists():
                logger.warning(
                    f"{self.name} Ignored host {ansible_host} because "
                    f"associated keyfile {keyfile} does not exist"
                )
                continue

            host = {
                'address': ansible_host,
                'username': ansible_user,
                'password': password,
                'namespace': self._namespace,
                'ssh_keyfile': keyfile,
                'port': port,
                'devtype': devtype,
                'transport': transport,
                'hostname': None
            }
            out_inv[f"{self._namespace}.{ansible_host}.{port}"] = host

        return out_inv
