# pylint: disable=no-name-in-module
# pylint: disable=no-self-argument
import logging
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator
from suzieq.poller.controller.source.base_source import Source, SourceModel
from suzieq.poller.controller.utils.inventory_utils import validate_hostname
from suzieq.shared.utils import PollerTransport

logger = logging.getLogger(__name__)


class HostModel(BaseModel):
    """Model used to validate the hosts of a native inventory
    """
    username: str = Field(default=None)
    password: Optional[str] = Field(default=None)
    keyfile: Optional[str] = Field(default=None)
    devtype: Optional[str] = Field(default=None)
    port: Optional[str] = Field(default=None)
    address: str = Field(default=None)
    transport: str = Field(default=None)
    url: str

    @validator('url')
    def validate_and_set(cls, url: str, values):
        """Validate the 'url' parameter and set the other parameters
        """
        words = url.split()
        decoded_url = urlparse(words[0])

        username = decoded_url.username
        password = (decoded_url.password or
                    # self.user_password or #I can't get this info here
                    None)
        address = decoded_url.hostname
        if not validate_hostname(address):
            raise ValueError(f'Invalid hostname or address {address}')
        transport = decoded_url.scheme or "https"
        try:
            PollerTransport[transport]
        except KeyError:
            raise ValueError(
                f"Transport '{transport}' not supported for host {address}")
        port = decoded_url.port
        devtype = None
        keyfile = None

        try:
            for i in range(1, len(words[1:])+1):
                if words[i].startswith('keyfile'):
                    keyfile = words[i].split('=')[1]
                elif words[i].startswith('devtype'):
                    devtype = words[i].split('=')[1]
                elif words[i].startswith('username'):
                    username = words[i].split('=')[1]
                elif words[i].startswith('password'):
                    password = words[i].split('=')[1]
                else:
                    raise ValueError(
                        f'Unknown parameter: {words[i]} for {address}')
        except IndexError:
            if 'password' not in words[i]:
                raise ValueError(f"Missing '=' in key {words[i]}")
            raise ValueError("Invalid password spec., missing '='")

        if keyfile and not Path(keyfile).exists():
            raise ValueError(
                f"keyfile {keyfile} does not exist"
            )

        values['username'] = username
        values['password'] = password
        values['keyfile'] = keyfile
        values['devtype'] = devtype
        values['port'] = port
        values['address'] = address
        values['transport'] = transport

        return url


class NativeSourceModel(SourceModel):
    """Native source validation model
    """
    hosts: List[HostModel]

    @validator('hosts')
    def hosts_not_empty(cls, hosts: List):
        """checks if the hosts list is not empty"""
        if not hosts:
            raise ValueError('Empty hosts list')
        return hosts


class SqNativeFile(Source):
    """Source class used to load Suzieq native inventory files
    """

    def __init__(self, input_data, validate: bool = True) -> None:
        self._cur_inventory = {}
        super().__init__(input_data, validate)

    @classmethod
    def get_data_model(cls):
        return NativeSourceModel

    def _load(self, input_data):
        if not self._validate:
            new_hosts = []
            for h in input_data.get('hosts', []):
                new_hosts.append(HostModel(**h))
            input_data['hosts'] = new_hosts
        super()._load(input_data)

        self._cur_inventory = self._get_inventory()
        self.set_inventory(self._cur_inventory)

    def _get_inventory(self) -> Dict:
        """Extract the data from ansible inventory file

        Returns:
            Dict: inventory dictionary
        """
        inventory = {}

        for host in self._data.hosts:
            # I cannot use host.dict() due to field names changing
            entry = {
                'address': host.address,
                'username': host.username,
                'port': host.port,
                'password': host.password,
                'transport': host.transport,
                'devtype': host.devtype,
                'namespace': self._namespace,
                'ssh_keyfile': host.keyfile,
                'hostname': None,
            }
            inventory[f'{self._namespace}.{host.address}.{host.port}'] = entry

        if not inventory:
            logger.error('No hosts detected in provided inventory file')

        return inventory
