"""StaticPollerManager module

    This module contains a simple PollerManager which only writes
    inventory chunks on different files for the pollers
"""
from os.path import isdir, join
from subprocess import Popen
from typing import List, Dict
import yaml
from suzieq.inventory_provider.plugins.poller_manager.poller_manager \
    import PollerManager


class StaticPollerManager(PollerManager):
    """The StaticPollerManager writes the inventory chunks on files

    The number of pollers is defined in the configuration file with
    the path for inventory files
    """

    def __init__(self, config_data):

        if not config_data:
            raise ValueError("No configuration provided")

        self._pollers_count = config_data.get("pollers_count", 1)
        self._inventory_path = config_data.get("inventory_path", None)
        if not self._inventory_path or not isdir(self._inventory_path):
            raise RuntimeError(
                f"Invalid inventory path: {self._inventory_path}")

        self._inventory_file_name = config_data \
            .get("inventory_file_name", "inventory")

        self._start_pollers = config_data.get("start_pollers", True)

    def apply(self, inventory_chunks: List[Dict]):
        """Write inventory chunks on files

        Args:
            inventory_chunks (List[Dict]): input inventory chunks
        """
        for i, inventory in enumerate(inventory_chunks):

            cur_inventory = {}
            for device in inventory.values():
                hostname = device.get("hostname", "")

                ipv4_address = device.get("ipv4", None)
                ipv6_address = device.get("ipv6", None)
                if not (ipv4_address or ipv6_address):
                    raise RuntimeError(f"device {hostname} has no "
                                       "ip addresses")
                if ipv4_address:
                    ipv4_address = ipv4_address.split("/")[0]

                if ipv6_address:
                    ipv6_address = ipv6_address.split("/")[0]

                transport = device.get("method", "ssh")

                cur_ns = device.get("namespace", None)
                if cur_ns is None:
                    raise RuntimeError(f"device {hostname} has no "
                                       "namespace")

                credentials = device.get("credentials", None)
                if not credentials or not isinstance(credentials, dict):
                    raise RuntimeError(f"device {hostname} has invalid "
                                       f"credentials")

                username = credentials.get("username", None)
                password = credentials.get("password", None)
                key_path = credentials.get("key_path", None)
                if not (username and (password or key_path)):
                    raise RuntimeError(f"device {hostname} has invalid "
                                       "credentials")

                options = credentials.get("options", {})
                if not isinstance(options, dict):
                    raise RuntimeError(f"device {hostname} has invalid "
                                       "options")

                hostline = f'{transport}://{username}@' \
                    f'{ipv4_address or ipv6_address}'

                if transport == "ssh":
                    hostline += f':{device.get("port",22)}'
                else:
                    hostline += f':{device.get("port",443)}'

                if password:
                    hostline += f' password={password}'
                else:
                    hostline += f' keyfile={key_path}'

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
