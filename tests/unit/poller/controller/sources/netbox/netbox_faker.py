import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from faker import Faker

_BASIC_DEVICE_DATA_PATH = 'tests/unit/poller/controller/sources/netbox/data/'\
    'faker/base_device.json'
_VALID_OUTPUT_FORMATS = ["json"]

_BASE_INVENTORY_DEVICE = {
    'address': '',
    'devtype': None,
    'enable_password': None,
    'hostname': '',
    'ignore_known_hosts': False,
    'jump_host': None,
    'jump_host_key_file': None,
    'namespace': '',
    'passphrase': None,
    'password': 'password',
    'port': 22,
    'slow_host': False,
    'per_cmd_auth': True,
    'retries_on_auth_fail': 0,
    'ssh_keyfile': None,
    'transport': 'ssh',
    'username': 'username'
}

_DEFAULT_TAG = {
    'id': 1,
    'url': 'http://127.0.0.1:800',
    'display': 'suzieq',
    'name': 'suzieq',
    'slug': 'suzieq',
    'color': '673ab7'
}


class NetboxFaker:
    """This class generates fake data for Netbox REST server and create
    the expected inventory file
    """

    def __init__(self, config_data: dict) -> None:
        """ config_data is the following:

            count: int          # number of devices (Default 1)
            tag-value: str      # devices tag (Default 'suzieq')
            tag-prob: float     # probability that a device has the tag
                                # (Default 1)
            ip4-prob: float     # probability that a device has an ipv4
                                # (Default 1)
            ip6-prob: float     # probability that a device has an ipv6
                                # (Default 1)
            namespace: str      # devices namespace in the inventory file
            site-count: int     # number of sites
            seed: int           # faker seed
        """
        base_path = Path(_BASIC_DEVICE_DATA_PATH)
        if not base_path.is_file():
            raise ValueError("invalid basic device path")

        with open(base_path, "r") as f:
            self._base_device = json.loads(f.read())

        self._fake = Faker()
        self.devices = []

        seed = config_data.get('seed')
        if seed:
            Faker.seed(seed)
        self.device_count = config_data.get("count", 1)
        self._dev_tags = config_data.get("tag-value", ['suzieq'])
        self._tag_values = self.create_tag_values()
        self._dev_tag_prob = config_data.get("tag-prob", 1)
        self._ip4_prob = config_data.get("ip4-prob", 1)
        self._ip6_prob = config_data.get("ip6-prob", 1)
        self._namespace = config_data.get('namespace', 'netbox-ns')

        sites_set = set()
        site_count = config_data.get("site-count", 1)
        while len(sites_set) < site_count:
            sites_set.add(self._fake.company())
        self._sites = list(sites_set)

        # The sort list is mandatory because otherwise the set -> list cast
        # can result in a different order every run of the code
        self._sites.sort()

    def create_tag_values(self) -> List[Dict]:
        """Create the tag part of the response

        Returns:
            List[Dict]: list of tag response body
        """
        tag_values = []
        for i, tag in enumerate(self._dev_tags):
            cur_tag = _DEFAULT_TAG.copy()
            cur_tag.update({
                'name': tag,
                'display': tag,
                'slug': tag.lower(),
                'id': i
            })
            tag_values.append(cur_tag)
        return tag_values

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

    def setTag(self, index: int, tag_index: int):
        """Set device tag

        Args:
            index (int): index of device
            tag_index (int): index of the tag to set
        """
        tag_list = self.devices[index].get("tags")
        tag_list.append(self._tag_values[tag_index])

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

    def generate_data(self) -> Tuple[Dict, Dict]:
        """Generate the list of devices with random values
        and the expected netbox inventory

        Returns:
            Tuple[Dict, Dict]: server_data, exp_inventory
        """
        exp_inventory = {}
        # Generate devicces
        for i in range(self.device_count):
            tag_set = False
            ip_set = False
            self.devices.append(deepcopy(self._base_device))
            self.set_dev_attr(i, 'id', i)

            dev_name = self._fake.slug()
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

            # tag
            if self._fake.pyfloat(min_value=0, max_value=1) \
                    < self._dev_tag_prob and self._dev_tags:
                n_tags = self._fake.pyint(
                    min_value=1, max_value=len(self._dev_tags))
                tag_index_set = set()
                for _ in range(n_tags):
                    while True:
                        tag_index = self._fake.pyint(
                            min_value=0, max_value=len(self._dev_tags)-1)
                        if tag_index not in tag_index_set:
                            tag_index_set.add(tag_index)
                            break
                    self.setTag(i, tag_index)
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

        server_data = dict(
            results=self.devices
        )

        return server_data, exp_inventory
