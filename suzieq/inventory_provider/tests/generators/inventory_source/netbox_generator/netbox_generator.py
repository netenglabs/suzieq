from faker import Faker
from suzieq.inventory_provider.tests.generators.base_generators.inventory_source import InventorySourceGenerator
from copy import deepcopy
from os.path import dirname, join, isfile, isdir
import json

_CUR_FILE_PATH = dirname(__file__)
_BASIC_DEVICE_DATA_PATH = join(_CUR_FILE_PATH, "common/base_device.json")
_BASIC_TOKEN_DATA_PATH = join(_CUR_FILE_PATH, "common/base_token.json")
_VALID_OUTPUT_FORMATS = ["json"]


class NetboxGenerator(InventorySourceGenerator):
    def __init__(self, name: str, fake: Faker, config_data: dict) -> None:
        '''
        Initialize the FakeSource

        devices:
        - _base_device: data structure which contains a template for a device
        - _fake: Faker object
        - devices: list of created devices
        - device_count: number of devices
        - _dev_root_name: starting string of each device name
        - _dev_tag: devices tag
        - _dev_tag_prob: probability that a device has a tag
        - _ip4_prob: probability that a device has an ipv4 ip
        - _ip6_prob: probability that a device has an ipv6 ip
        - _sites: the ordered list of site-names
        '''

        self._gen_name = name

        # load device informations
        if not isfile(_BASIC_DEVICE_DATA_PATH):
            raise ValueError("invalid basic device path")

        with open(_BASIC_DEVICE_DATA_PATH, "r") as f:
            base_device = json.loads(f.read())
        self._base_device = base_device

        devices_info = config_data.get("devices", None)
        if not devices_info:
            raise ValueError("Config file doesn't have field 'device'")

        self._fake: Faker = fake
        self.devices = []
        self.device_count = devices_info.get("count", 1)
        self._dev_root_name = devices_info.get("name", "device")
        tag_data = devices_info.get("tag", {})
        self._dev_tag = tag_data.get("value", None)
        self._dev_tag_prob = tag_data.get("prob", 1)
        ip_data = devices_info.get("ip", {})
        self._ip4_prob = ip_data.get("prob", {}).get("4", 1)
        self._ip6_prob = ip_data.get("prob", {}).get("6", 1)

        sites_set = set()
        site_count = devices_info.get("site_count", 1)
        while len(sites_set) < site_count:
            sites_set.add(self._fake.company())
        self._sites = list(sites_set)

        # The sort list is mandatory because otherwise the set -> list cast
        # can result in a different order every run of the code
        self._sites.sort()

        self._dev_out_path = devices_info.get("out_path", "")
        if not self._dev_out_path:
            raise RuntimeError("You must specify an out_path for devices")
        self._dev_out_format = devices_info.get("out_format", "json")
        self._dev_out_file = f"{self._gen_name}.{self._dev_out_format}"

        # Load tokens info
        if not isfile(_BASIC_TOKEN_DATA_PATH):
            raise ValueError("invalid basic device path")

        with open(_BASIC_TOKEN_DATA_PATH, "r") as f:
            base_token = json.loads(f.read())
        self._base_token = base_token

        tokens_info = config_data.get("tokens", None)
        if not tokens_info:
            raise ValueError("Config file doesn't have field 'tokens'")

        self._tokens = []
        self._token_values = tokens_info.get("list", [])
        self._token_out_path = tokens_info.get("out_path", "")
        if not self._dev_out_path:
            raise RuntimeError("You must specify an out_path for devices")
        self._token_out_format = tokens_info.get("out_format", "json")
        self._token_out_file = f"{self._gen_name}.{self._token_out_format}"

    def setDevAttr(self, index: int, key: str, value):
        '''
        Create or overwrite the content of <key> of device <index>
        with <value>
        '''
        if index > len(self.devices):
            raise RuntimeError("Index out of range")

        self.devices[index][key] = value

    def setIP(self, index: int, ip_addr: str, version: int):
        '''
        Set the values related on the ip depending on the version
        '''
        if version not in [4, 6]:
            raise ValueError("Unknown ip version {}".format(version))

        ip_key = "primary_ip{}".format(version)
        ip_dict = self.devices[index].get(ip_key, None)
        if ip_dict is None:
            raise RuntimeError("Unknown key {}".format(ip_key))
        ip_dict["address"] = ip_addr
        ip_dict["display"] = ip_addr
        ip_dict["family"] = version

        self.setDevAttr(index, ip_key, ip_dict)

    def setTag(self, index, tag: str):
        '''
        Set the values regarding to the tag
        '''
        tag_list = self.devices[index].get("tags", None)
        if tag_list is None:
            raise RuntimeError("Unknown key {}".format("tags"))
        tag_list[0]["name"] = tag
        tag_list[0]["display"] = tag
        tag_list[0]["slug"] = tag.lower()

        self.setDevAttr(index, "tags", tag_list)

    def setSite(self, index, site_name: str):
        '''
        Set the values regarding the site
        '''
        site_dict = self.devices[index].get("site", None)
        if site_dict is None:
            raise RuntimeError("Unknown key {}".format("site"))
        site_dict["name"] = site_name
        site_dict["display"] = site_name
        site_dict["slug"] = site_name.lower()

        self.setDevAttr(index, "site", site_dict)

    def setDevName(self, index, dev_name: str):
        '''
        Set the values regarding the device name
        '''
        self.setDevAttr(index, "name", dev_name)
        self.setDevAttr(index, "display", dev_name)

    def writeData(self, output, path, format):
        if not isdir(dirname(path)):
            raise RuntimeError("Invalid path {}".format(dirname(path)))

        if format not in _VALID_OUTPUT_FORMATS:
            raise RuntimeError("Unsupported output format {}"
                               .format(format))

        with open(path, "w") as f:
            if format == "json":
                f.write(json.dumps(output))

    def _generate_data(self):
        '''
        Generate the list of devices and tokens with random values

        If the flake seed is set, the same configuration file will produce
        the same output
        '''
        # Generate devicces
        for i in range(self.device_count):
            self.devices.append(deepcopy(self._base_device))

            dev_name = "{}-{}".format(self._dev_root_name, self._fake.slug())
            self.setDevName(i, dev_name)

            dev_site = self._sites[
                self._fake.pyint(min_value=0, max_value=len(self._sites) - 1)
            ]
            self.setSite(i, dev_site)

            # ipv4
            if self._fake.pyfloat(min_value=0, max_value=1) < self._ip4_prob:
                ip = self._fake.ipv4()
                mask = self._fake.pyint(min_value=0, max_value=32, step=8)
                ip_addr = "{}/{}".format(ip, mask)
                self.setIP(i, ip_addr, 4)
            else:
                self.setDevAttr(i, "primary_ip4", None)

            # ipv6
            if self._fake.pyfloat(min_value=0, max_value=1) < self._ip6_prob:
                ip = self._fake.ipv6()
                mask = self._fake.pyint(min_value=64, max_value=128, step=8)
                ip_addr = "{}/{}".format(ip, mask)
                self.setIP(i, ip_addr, 6)
            else:
                self.setDevAttr(i, "primary_ip6", None)

            if self._fake.pyfloat(min_value=0, max_value=1) \
                    < self._dev_tag_prob and self._dev_tag:
                self.setTag(i, self._dev_tag)
            else:
                self.setDevAttr(i, "tags", None)

        device_out_data = dict(
            results=self.devices
        )

        dev_out_path = join(
            _CUR_FILE_PATH,
            self._dev_out_path,
            self._dev_out_file
        )

        self.writeData(device_out_data, dev_out_path, self._dev_out_format)

        # Generate tokens
        for i, token_val in enumerate(self._token_values):
            self._tokens.append(deepcopy(self._base_token))

            self._tokens[i]["key"] = token_val

        token_out_path = join(
            _CUR_FILE_PATH,
            self._token_out_path,
            self._token_out_file
        )

        self.writeData(self._tokens, token_out_path, self._token_out_format)

    def _generate_credentials(self):
        pass
