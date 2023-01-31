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
from typing import Any, Dict, List, Optional, Tuple, Union
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
    tag: Optional[Any] = Field(default=['suzieq'])
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

    @validator('tag')
    def validate_tag(cls, tags):
        """checks if the tag is a list or a string. It always returns a list
        """
        # This validator is implemented to avoid the users to update their
        # tags from string to list.
        # In future, 'tag' will be forced to be a list
        if not isinstance(tags, list):
            logger.warning(
                'Netbox: deprecated string format for tag. Use a list instead')
            tags = [tags]
        return [[t.strip() for t in tag.split(',')] for tag in tags]


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

    def _get_url_list(self) -> List[str]:
        """Return the list of requests to execute

        Returns:
            List[str]: list of urls
        """
        urls = []
        url_address = f'{self._server.protocol}://{self._server.host}:'\
            f'{self._server.port}/api/dcim/devices/?'
        for tags in self._data.tag:
            query = url_address
            for (i, t) in enumerate(tags):
                if i > 0:
                    query += '&'
                query += f'tag={t}'
            urls.append(query)
        return urls

    async def get_inventory_list(self) -> List:
        """Contact netbox to retrieve the inventory.

        If more than one tag is set, all devices that have at least one of the
        tags are selected. Netbox api doesn't allow to select with this
        logic by default. If the url query is constructed like
        '?tag=tag1&tag=tag2', only devices with both tags will be returned.
        For this reason, a different request for each tag must be performed.

        Devices with more than one tag may appear duplicated. It's also
        necessary to drop duplicates.

        Raises:
            RuntimeError: Unable to connect to the REST server

        Returns:
            List: inventory list
        """

        if not self._session:
            headers = self._token_auth_header()
            self._init_session(headers)

        # devices is a dictionary to avoid duplicated devices. The key of the
        # dictionary is the device netbox id.
        devices = {}
        try:
            for url in self._get_url_list():
                logger.debug(f"Netbox: Retrieving url '{url}'")
                url_devices, next_url = await self._get_devices(url)
                while next_url:
                    logger.debug(f"Netbox: Retrieving url '{next_url}'")
                    cur_devices, next_url = await self._get_devices(next_url)
                    url_devices.extend(cur_devices)
                devices.update({device['id']: device for device in url_devices
                                if device.get('id') is not None})
        except Exception as e:
            raise InventorySourceError(f'{self.name}: error while '
                                       f'getting devices: {e}')

        logger.info(
            f'Netbox: Retrieved inventory list of {len(devices)} devices')
        return list(devices.values())

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
                next_url = res.get('next')
                if next_url:
                    # The next url might contain a different url if netbox is
                    # behind a reverse proxy.
                    # The code below sets the protocol, the host and the port
                    # of the next request to the same parameters of the
                    # previous request which was successful

                    logger.debug(f'Parsing next page url {next_url}')

                    # parse urls
                    url_data = urlparse(url)
                    next_url_data = urlparse(next_url)

                    # retrieve protocol, host and port from the urls
                    host = url_data.hostname
                    protocol = url_data.scheme or 'http'
                    port = url_data.port or _DEFAULT_PORTS.get(protocol)

                    next_host = next_url_data.hostname
                    next_protocol = next_url_data.scheme or 'http'
                    next_port = (next_url_data.port or
                                 _DEFAULT_PORTS.get(next_protocol))

                    # verify if the two elements are different. If so, log
                    # what's different and set the value to content of the
                    # previous url
                    if host != next_host:
                        logger.debug(
                            'Detected a different host in response: original '
                            f'host "{host}", received host "{next_host}". '
                            f'Setting the request host to "{host}"'
                        )
                        next_host = host
                    if protocol != next_protocol:
                        logger.debug(
                            'Detected a different protocol in response: '
                            f'original protocol "{protocol}", received '
                            f'protocol "{next_protocol}". Setting the request '
                            f'protocol to "{protocol}"'
                        )
                        next_protocol = protocol
                    if port != next_port:
                        logger.debug(
                            'Detected a different port in response: original '
                            f'port "{port}", received port "{next_port}". '
                            f'Setting the request port to "{port}"'
                        )
                        next_port = port

                    # build the next_url
                    next_url = (f'{next_protocol}://{next_host}:{next_port}'
                                f'{next_url_data.path}?{next_url_data.query}')
                return res.get('results', []), next_url
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
        ignored_device_count = 0

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
                ignored_device_count += 1
                continue

            address = address.split("/")[0]

            inventory[f'{namespace}.{address}'] = {
                'address': address,
                'namespace': namespace,
                'hostname': hostname,
            }

        logger.info(
            f'Netbox: Acting on inventory of {len(inventory)} devices, '
            f'ignoring {ignored_device_count} devices')

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
