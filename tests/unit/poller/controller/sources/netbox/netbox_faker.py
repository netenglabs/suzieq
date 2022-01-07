import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from faker import Faker

_BASIC_DEVICE_DATA_PATH = 'tests/unit/poller/controller/sources/netbox/data/'\
    'faker/base_device.json'
_VALID_OUTPUT_FORMATS = ["json"]

_BASE_INVENTORY_DEVICE = {
    'address': '',
    'devtype': None,
    'hostname': '',
    'ignore_known_hosts': None,
    'jump_host': None,
    'jump_host_key_file': None,
    'namespace': '',
    'passphrase': None,
    'password': 'password',
    'port': 22,
    'ssh_keyfile': None,
    'transport': 'ssh',
    'username': 'username'
}


class NetboxFaker:
    """This class generates fake data for Netbox REST server and create
    the expected inventory file
    """
    def __init__(self, config_data: dict) -> None:
        base_path = Path(_BASIC_DEVICE_DATA_PATH)
        if not base_path.is_file():
            raise ValueError("invalid basic device path")

        with open(base_path, "r") as f:
            self._base_device = json.loads(f.read())

        self._fake = Faker()
        self.devices = []
        self.device_count = config_data.get("count", 1)
        self._dev_root_name = config_data.get("name", "device")
        self._dev_tag = config_data.get("tag-value", 'suzieq')
        self._dev_tag_prob = config_data.get("tag-prob", 1)
        self._ip4_prob = config_data.get("ip4-prob", 1)
        self._ip6_prob = config_data.get("ip6-prob", 1)
        self._namespace = config_data.get('namespace', 'netbox-ns')

        sites_set = set()
        site_count = config_data.get("site_count", 1)
        while len(sites_set) < site_count:
            sites_set.add(self._fake.company())
        self._sites = list(sites_set)

        # The sort list is mandatory because otherwise the set -> list cast
        # can result in a different order every run of the code
        self._sites.sort()

        self._dev_out_path = config_data.get("server_out_path", "")
        if not self._dev_out_path:
            raise RuntimeError("You must specify an out_path for devices")
        self._inventory_out_path = config_data.get("inventory_out_path", "")
        if not self._inventory_out_path:
            raise RuntimeError("You must specify an out_path for devices")
        self._dev_out_format = config_data.get("out_format", "json")
        # self._dev_out_file = f"{self._gen_name}.{self._dev_out_format}"

    def set_dev_attr(self, index: int, key: str, value):
        """Create or overwrite the content of <key> of device <index>
        with <value>

        Args:
            index (int): self.devices index
            key (str): key to create/replace
            value ([type]): value to insert

        Raises:
            RuntimeError: index out of range
        """
        if index > len(self.devices):
            raise RuntimeError("Index out of range")

        self.devices[index][key] = value

    def set_ip(self, index: int, ip_addr: str, version: int):
        """Set the ip address

        Args:
            index (int): index in self.devices
            ip_addr (str): ip address
            version (int): ip version (4, 6)

        Raises:
            ValueError: Unknown ip version
        """
        if version not in [4, 6]:
            raise ValueError(f"Unknown ip version {version}")

        ip_key = f"primary_ip{version}"
        ip_dict = self.devices[index].get(ip_key)
        ip_dict["address"] = ip_addr
        ip_dict["display"] = ip_addr
        ip_dict["family"] = version

        self.set_dev_attr(index, ip_key, ip_dict)

    def setTag(self, index: int, tag: str):
        """Set device tag

        Args:
            index (int): index of device
            tag (str): tag to set
        """
        tag_list = self.devices[index].get("tags")
        tag_list[0]["name"] = tag
        tag_list[0]["display"] = tag
        tag_list[0]["slug"] = tag.lower()

        self.set_dev_attr(index, "tags", tag_list)

    def set_site_name(self, index: int, site_name: str):
        """Set device site name

        Args:
            index (int): index of the device
            site_name (str): site name to set
        """
        site_dict = self.devices[index].get("site")
        site_dict["name"] = site_name
        site_dict["display"] = site_name
        site_dict["slug"] = site_name.lower()

        self.set_dev_attr(index, "site", site_dict)

    def set_hostname(self, index: int, hostname: str):
        """Set device hostname

        Args:
            index (int): index of device
            hostname (str): hostname to set
        """
        self.set_dev_attr(index, "name", hostname)
        self.set_dev_attr(index, "display", hostname)

    def write_data(self, output: Any, path: str, out_format: str):
        """Write <output> on file <path> with format <out_format>

        Args:
            output (Any): data to write
            path (str): output file path
            out_format (str): output file format

        Raises:
            RuntimeError: invalid file or format
        """
        p = Path(path)
        if not p.parent.is_dir():
            raise RuntimeError(f"Invalid path {p.parent}")

        if out_format not in _VALID_OUTPUT_FORMATS:
            raise RuntimeError("Unsupported output format {}"
                               .format(out_format))

        with open(path, "w") as f:
            if out_format == "json":
                f.write(json.dumps(output))

    def generate_data(self):
        '''
        Generate the list of devices and tokens with random values

        If the flake seed is set, the same configuration file will produce
        the same output
        '''
        exp_inventory = {}
        # Generate devicces
        for i in range(self.device_count):
            tag_set = False
            ip_set = False
            self.devices.append(deepcopy(self._base_device))

            dev_name = "{}-{}".format(self._dev_root_name, self._fake.slug())
            self.set_hostname(i, dev_name)

            dev_site = self._sites[
                self._fake.pyint(min_value=0, max_value=len(self._sites) - 1)
            ]
            self.set_site_name(i, dev_site)

            # ipv6
            if self._fake.pyfloat(min_value=0, max_value=1) < self._ip6_prob:
                ip = self._fake.ipv6()
                mask = self._fake.pyint(min_value=64, max_value=128, step=8)
                ip_addr = "{}/{}".format(ip, mask)
                self.set_ip(i, ip_addr, 6)
                ip_set = True
            else:
                self.set_dev_attr(i, "primary_ip6", None)

            # ipv4
            if self._fake.pyfloat(min_value=0, max_value=1) < self._ip4_prob:
                ip = self._fake.ipv4()
                mask = self._fake.pyint(min_value=0, max_value=32, step=8)
                ip_addr = "{}/{}".format(ip, mask)
                self.set_ip(i, ip_addr, 4)
                ip_set = True
            else:
                self.set_dev_attr(i, "primary_ip4", None)

            if self._fake.pyfloat(min_value=0, max_value=1) \
                    < self._dev_tag_prob and self._dev_tag:
                self.setTag(i, self._dev_tag)
                tag_set = True
            else:
                self.set_dev_attr(i, "tags", None)

            if tag_set and ip_set:
                # only devices with an ip and the correct tag
                # are saved into the netbox inventory
                if self._namespace == 'netbox-sitename':
                    namespace = dev_site
                else:
                    namespace = self._namespace
                dev_key = f'{namespace}.{ip}'
                exp_inventory[dev_key] = _BASE_INVENTORY_DEVICE.copy()

                exp_inventory[dev_key].update({
                    'address': ip,
                    'hostname': dev_name,
                    'namespace': namespace
                })

        device_out_data = dict(
            results=self.devices
        )

        self.write_data(device_out_data, self._dev_out_path,
                        self._dev_out_format)

        self.write_data(exp_inventory, self._inventory_out_path,
                        self._dev_out_format)
