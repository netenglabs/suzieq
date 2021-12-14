"""
This module contains the logic of the plugin in charge of importing an
inventory from an Ansible inventory file.
"""

from typing import Dict, List

from suzieq.poller.worker.inventory.inventory_sources_base.inventory import Inventory
from suzieq.shared.inventories_parsing import parse_ansible_inventory


class AnsibleInventory(Inventory):
    """The AnsibleInventory is a class allowing to import the output
    of 'ansible-inventory command' as input of the poller.
    """

    def __init__(self, add_task_fn, **kwargs) -> None:
        self.ansible_file = kwargs.pop('ansible_file', None)
        self.default_namespace = kwargs.pop('default_namespace', None)
        super().__init__(add_task_fn, **kwargs)

    def _get_device_list(self) -> List[Dict]:
        """Extract the data from the Ansible inventory file

        Returns:
            List[Dict]: list with the data to connect to the devices in the
                inventory
        """
        return parse_ansible_inventory(self.ansible_file,
                                       self.default_namespace)
