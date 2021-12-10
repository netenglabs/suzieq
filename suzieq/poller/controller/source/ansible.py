"""
This module contains the logic of the plugin in charge of importing an
inventory from an Ansible inventory file.
"""
from os.path import isfile
from typing import Dict, List
from suzieq.poller.controller.source.base_source import Source
from suzieq.shared.exceptions import InventorySourceError
# TODO: parse_ansible_inventory should be moved here
from suzieq.shared.inventories_parsing import parse_ansible_inventory


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
        # TODO: Add this into parse_ansible_inventory when moved
        for i, item in enumerate(inventory):
            item["id"] = str(i)
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
        """Extract the data from the Ansible inventory file

        Returns:
            List[Dict]: list with the data to connect to the devices in the
                inventory
        """
        return parse_ansible_inventory(self.ansible_file,
                                       self.namespace)
