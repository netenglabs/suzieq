"""StaticPollerManager module

    This module contains a simple PollerManager which only writes
    inventory chunks on different files for the pollers
"""
from os.path import isdir, join
from subprocess import Popen
from typing import List, Dict
import yaml
from suzieq.poller.controller.manager.base_manager \
    import BaseManager


class StaticManager(BaseManager):
    """The StaticPollerManager writes the inventory chunks on files

    The number of pollers is defined in the configuration file with
    the path for inventory files
    """

    def __init__(self, config_data: dict = None):

        self._pollers_count = config_data.get("pollers_count", 1)
        self._inventory_path = config_data.get(
            "inventory_path", "suzieq/.poller/intentory/static_inventory")
        if not self._inventory_path or not isdir(self._inventory_path):
            raise RuntimeError(
                f"Invalid inventory path: {self._inventory_path}")

        self._inventory_file_name = config_data \
            .get("inventory_file_name", "static_inv")

        self._start_pollers = config_data.get("start_pollers", True)

    def apply(self, inventory_chunks: List[Dict]):
        """Write inventory chunks on files

        Args:
            inventory_chunks (List[Dict]): input inventory chunks
        """
        for i, inventory in enumerate(inventory_chunks):

            cur_inventory = {}
            for device in inventory.values():

                address = device.get("address", None)
                if not address:
                    raise RuntimeError("device has no "
                                       "ip addresses")
                if address.find("/") != -1:
                    address = address.split("/")[0]

                transport = device.get("transport", "ssh")

                cur_ns = device.get("namespace", None)
                if cur_ns is None:
                    raise RuntimeError(f"device {address} has no "
                                       "namespace")

                username = device.get("username", None)
                password = device.get("password", None)
                ssh_keyfile = device.get("ssh_keyfile", None)
                if transport == "ssh" and \
                        not (username and (password or ssh_keyfile)):
                    raise RuntimeError(f"device {address} has invalid "
                                       "credentials")

                options = device.get("options", {})
                if not isinstance(options, dict):
                    raise RuntimeError(f"device {address} has invalid "
                                       "options")

                port = device.get("port")
                if not port:
                    raise RuntimeError(f"device {address} unknow port")

                hostline = f'{transport}://{username}@' \
                    f'{address}'

                if transport == "ssh":
                    hostline += f':{device.get("port",22)}'
                else:
                    hostline += f':{device.get("port",80)}'

                if password:
                    hostline += f' password={password}'
                elif ssh_keyfile:
                    hostline += f' keyfile={ssh_keyfile}'

                if cur_ns not in cur_inventory:
                    cur_inventory[cur_ns] = {
                        "namespace": cur_ns,
                        "hosts": []
                    }
                cur_inventory[cur_ns]["hosts"].append({"url": hostline})

            if cur_inventory:
                out_file_path = join(
                    self._inventory_path,
                    f"{self._inventory_file_name}{i}.yaml"
                )

                with open(out_file_path, "w") as file:
                    file.write(yaml.safe_dump(list(cur_inventory.values())))

                if self._start_pollers:
                    Popen(["sq-poller", "-D", out_file_path, "-c",
                           "suzieq/config/etc/suzieq-cfg.yml"])
                    # Avoid the poller to start again
                    self._start_pollers = False

    def get_pollers_number(self, inventory: dict = None) -> int:
        """returns the content of self._poller_count statically loaded from
           the configuration file

        Attention: This function doesn't use the inventory

        Args:
            inventory (dict, optional): The global inventory.

        Returns:
            int: number of desired pollers configured in the configuration
                 file
        """
        return self._pollers_count
