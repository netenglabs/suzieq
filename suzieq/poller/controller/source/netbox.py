"""Netbox module

This module contains the methods to connect with a Netbox REST server
and retrieve the devices inventory

Classes:
    Netbox: this class dinamically retrieve the inventory from Netbox
"""
import asyncio
import logging
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import aiohttp
from suzieq.poller.controller.inventory_async_plugin import \
    InventoryAsyncPlugin
from suzieq.poller.controller.source.base_source import Source
from suzieq.shared.exceptions import InventorySourceError

_DEFAULT_PORTS = {'http': 80, 'https': 443}

logger = logging.getLogger(__name__)


class Netbox(Source, InventoryAsyncPlugin):
    """This class is used to dinamically retrieve the inventory from Netbox
       and also retrieve for each device in the inventory its credentials

    """

    def __init__(self, config_data: dict) -> None:
        self._status = 'init'
        self._session: aiohttp.ClientSession = None
        self._tag = ''
        self._host = ''
        self._namespace = ''
        self._period = 3600
        self._run_once = ''
        self._token = ''

        super().__init__(config_data)

    def _load(self, input_data: dict):
        """Load the configuration data in the object

        Args:
            input_data ([dict]): Input configuration data

        Raises:
            InventorySourceError: invalid config
        """

        if not input_data:
            raise InventorySourceError('no netbox_config provided')

        url = input_data.get('url', '')
        if not url:
            raise InventorySourceError(f'{self._name}: <url> not provided')

        url_data = urlparse(url)
        self._protocol = url_data.scheme or 'http'
        self._port = url_data.port or _DEFAULT_PORTS.get(self._protocol, None)
        self._host = url_data.hostname

        if not self._protocol or not self._port or not self._host:
            raise InventorySourceError(f'{self._name}: invalid url provided')

        self._tag = input_data.get('tag', 'null')
        self._namespace = input_data.get('namespace', 'site.name')
        self._period = input_data.get('period', 3600)
        self._run_once = input_data.get('run_once', False)
        self._token = input_data.get('token', None)

        logger.debug(f"Source {self._name} load completed")

    def _validate_config(self, input_data) -> list:
        """Validates the loaded configuration

        Returns:
            list: the list of errors
        """
        errors = []

        if not self._auth:
            return ["Netbox must have an 'auth' set"]

        if not input_data.get('token'):
            errors.append('No netbox token provided')
        if not input_data.get('url'):
            errors.append('No netbox url provided')
        if not input_data.get('auth'):
            errors.append('No device auth provided')
        return errors

    def _init_session(self, headers: dict):
        """Initialize the session property

        Args:
            headers ([dict]): headers to initialize the session
        """
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers=headers
            )

    def _token_auth_header(self) -> Dict:
        """Generate the token authorization header

        Returns:
            Dict: token authorization header
        """
        return {'Authorization': f'Token {self._token}'}

    async def get_inventory_list(self) -> List:
        """Contact netbox to retrieve the inventory.

        Raises:
            RuntimeError: Unable to connect to the REST server

        Returns:
            List: inventory list
        """
        url = f'{self._protocol}://{self._host}:{self._port}'\
            f'/api/dcim/devices/?tag={self._tag}'
        if not self._session:
            headers = self._token_auth_header()
            self._init_session(headers)
        try:
            devices, next_url = await self._get_devices(url)
            while next_url:
                cur_devices, next_url = await self._get_devices(next_url)
                devices.extend(cur_devices)
        except Exception as e:
            raise InventorySourceError(f'{self._name}: error while '
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
                    f'{self._name}: error in inventory get {response.status}')

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
            if self._namespace == 'site.name':
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
                f"Received netbox inventory from {self._protocol}"
                f"://{self._host}:{self._port}")
            tmp_inventory = self.parse_inventory(inventory_list)
            # Write the inventory and remove the tmp one
            self.set_inventory(tmp_inventory)

            if self._run_once:
                break

            await asyncio.sleep(self._period)

    async def _stop(self):
        if self._session:
            await self._session.close()
