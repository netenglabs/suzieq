"""Netbox module

This module contains the methods to connect with a Netbox REST server
and retrieve the devices inventory

Classes:
    Netbox: this class dinamically retrieve the inventory from Netbox
"""
# pylint: disable=no-name-in-module
# pylint: disable=no-self-argument

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from pydantic import BaseModel, validator, Field

import aiohttp
from suzieq.poller.controller.inventory_async_plugin import \
    InventoryAsyncPlugin
from suzieq.poller.controller.source.base_source import Source, SourceModel
from suzieq.shared.utils import get_sensitive_data
from suzieq.shared.exceptions import InventorySourceError, SensitiveLoadError

_DEFAULT_PORTS = {'http': 80, 'https': 443}

logger = logging.getLogger(__name__)


class NetboxServerModel(BaseModel):
    """Model containing data to connect with Netbox server
    """
    host: str
    protocol: str
    port: str

    class Config:
        """pydantic configuration
        """
        extra = 'forbid'


class NetboxSourceModel(SourceModel):
    """Netbox source validation model
    """
    tag: Optional[str] = Field(default='suzieq')
    period: Optional[int] = Field(default=3600)
    token: str
    ssl_verify: Optional[bool] = Field(alias='ssl-verify')
    server: Union[str, NetboxServerModel] = Field(alias='url')
    run_once: Optional[bool] = Field(default=False, alias='run_once')

    @validator('server', pre=True)
    def validate_and_set(cls, url, values):
        """Validate the field 'url' and set the correct parameters
        """
        if isinstance(url, str):
            url_data = urlparse(url)
            host = url_data.hostname
            if not host:
                raise ValueError(f'Unable to parse hostname {url}')
            protocol = url_data.scheme or 'http'
            if protocol not in _DEFAULT_PORTS:
                raise ValueError(f'Unknown protocol {protocol}')
            port = url_data.port or _DEFAULT_PORTS.get(protocol)
            if not port:
                raise ValueError(f'Unable to parse port {url}')
            server = NetboxServerModel(host=host, port=port, protocol=protocol)
            ssl_verify = values['ssl_verify']
            if ssl_verify is None:
                if server.protocol == 'http':
                    ssl_verify = False
                else:
                    ssl_verify = True
            else:
                if server.protocol == 'http' and ssl_verify:
                    raise ValueError(
                        'Cannot use ssl_verify=True with http host')
            values['ssl_verify'] = ssl_verify
            return server
        elif isinstance(url, NetboxServerModel):
            return url
        else:
            raise ValueError('Unknown input type')

    @validator('token')
    def validate_token(cls, token):
        """checks if the token can be load as sensible data
        """
        try:
            if token == 'ask':
                return token
            return get_sensitive_data(token)
        except SensitiveLoadError as e:
            raise ValueError(e)


class Netbox(Source, InventoryAsyncPlugin):
    """This class is used to dinamically retrieve the inventory from Netbox
       and also retrieve for each device in the inventory its credentials

    """

    def __init__(self, config_data: dict, validate: bool = True) -> None:
        self._status = 'init'
        self._session: aiohttp.ClientSession = None
        self._server: NetboxServerModel = None

        super().__init__(config_data, validate)

    @classmethod
    def get_data_model(cls):
        return NetboxSourceModel

    def _load(self, input_data):
        # load the server class from the dictionary
        if not self._validate:
            input_data['server'] = NetboxServerModel.construct(
                **input_data.pop('url', {}))
            input_data['ssl_verify'] = input_data.pop('ssl-verify', False)
        super()._load(input_data)
        if self._data.token == 'ask':
            self._data.token = get_sensitive_data(
                'ask', f'{self.name} Insert netbox API token: '
            )
        self._server = self._data.server
        if not self._auth:
            raise InventorySourceError(f"{self.name} Netbox must have an "
                                       "'auth' set in the 'namespaces' section"
                                       )

    def _init_session(self, headers: dict):
        """Initialize the session property

        Args:
            headers ([dict]): headers to initialize the session
        """
        if not self._session:
            ssl_option = None if self._data.ssl_verify else False
            self._session = aiohttp.ClientSession(
                headers=headers,
                connector=aiohttp.TCPConnector(ssl=ssl_option)
            )

    def _token_auth_header(self) -> Dict:
        """Generate the token authorization header

        Returns:
            Dict: token authorization header
        """
        return {'Authorization': f'Token {self._data.token}'}

    async def get_inventory_list(self) -> List:
        """Contact netbox to retrieve the inventory.

        Raises:
            RuntimeError: Unable to connect to the REST server

        Returns:
            List: inventory list
        """
        url = f'{self._server.protocol}://{self._server.host}:'\
            f'{self._server.port}/api/dcim/devices/?tag={self._data.tag}'
        if not self._session:
            headers = self._token_auth_header()
            self._init_session(headers)
        try:
            devices, next_url = await self._get_devices(url)
            while next_url:
                cur_devices, next_url = await self._get_devices(next_url)
                devices.extend(cur_devices)
        except Exception as e:
            raise InventorySourceError(f'{self.name}: error while '
                                       f'getting devices: {e}')
        return devices

    async def _get_devices(self, url: str) -> Tuple[List, str]:
        """Retrieve devices from netbox using an HTTP GET over <url>

        Args:
            url (str): devices url

        Raises:
            RuntimeError: Response error

        Returns:
            Tuple[List, str]: returns the list of devices and the url to get
            the remaining devices
        """
        async with self._session.get(url) as response:
            if int(response.status) == 200:
                res = await response.json()
                return res.get('results', []), res.get('next')
            else:
                raise InventorySourceError(
                    f'{self.name}: error in inventory get '
                    f'{await response.text()}')

    def parse_inventory(self, inventory_list: list) -> Dict:
        """parse the raw inventory collected from the server and generates
           a new inventory with only the required informations

        Args:
            raw_inventory (list): raw inventory received from the server

        Returns:
            List[Dict]: a list containing the inventory
        """
        def get_field_value(entry: dict, fields_str: str):
            # Fields_str is a string containing fields separated by dots
            # Every dot means that the value is deeper in the dictionary
            # Example: fields_str = 'site.name'
            #          return entry[site][name]
            fields = fields_str.split('.')
            cur_field = None
            for i, field in enumerate(fields):
                if i == 0:
                    cur_field = entry.get(field, None)
                else:
                    cur_field = cur_field.get(field, None)
                if cur_field is None:
                    return None
            return cur_field

        inventory = {}

        for device in inventory_list:
            ipv4 = get_field_value(device, 'primary_ip4.address')
            ipv6 = get_field_value(device, 'primary_ip6.address')
            hostname = get_field_value(device, 'name')
            site_name = get_field_value(device, 'site.name')
            if self._namespace == 'netbox-sitename':
                namespace = site_name
            else:
                namespace = self._namespace
            address = None

            if ipv4:
                address = ipv4
            elif ipv6:
                address = ipv6

            if not address:
                logger.warning(
                    f"Skipping {namespace}.{hostname}: doesn't have a "
                    "management IP")
                continue

            address = address.split("/")[0]

            inventory[f'{namespace}.{address}'] = {
                'address': address,
                'namespace': namespace,
                'hostname': hostname,
            }

        return inventory

    async def _execute(self):
        while True:
            inventory_list = await self.get_inventory_list()
            logger.debug(
                f"Received netbox inventory from {self._server.protocol}"
                f"://{self._server.host}:{self._server.port}")
            tmp_inventory = self.parse_inventory(inventory_list)
            # Write the inventory and remove the tmp one
            self.set_inventory(tmp_inventory)

            if self._run_once:
                break

            await asyncio.sleep(self._data.period)

    async def _stop(self):
        if self._session:
            await self._session.close()
