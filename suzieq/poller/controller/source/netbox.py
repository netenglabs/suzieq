"""Netbox module

This module contains the methods to connect with a Netbox REST server
and retrieve the devices inventory

Classes:
    Netbox: this class dinamically retrieve the inventory from Netbox
"""
import asyncio
import logging
from typing import Dict, List
from urllib.parse import urlparse

import aiohttp
from suzieq.poller.controller.inventory_async_plugin import \
    InventoryAsyncPlugin
from suzieq.poller.controller.source.base_source import Source
from suzieq.shared.exceptions import InventorySourceError

_DEFAULT_PORTS = {'http': 80, 'https': 443}
_RELEVANT_FIELDS = [
    'name',
    'primary_ip6.address',
    'primary_ip4.address',
    'site.name'
]

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
        # Contains CredentialLoader object with device credentials
        self._auth = None
        # Contains a dictionary with devices specifications
        self._device = None

        super().__init__(config_data)

    def _load(self, input_data: dict):
        """Load the configuration data in the object

        Args:
            input_data ([dict]): Input configuration data

        Raises:
            ValueError: netbox url is empty
            ValueError: netbox configuration
                        is empty
        """

        if not input_data:
            # error
            raise ValueError('no netbox_config provided')

        url = input_data.get('url', '')
        if not url:
            raise ValueError('netbox url not provided')

        url_data = urlparse(url)
        self._protocol = url_data.scheme or 'http'
        self._port = url_data.port or _DEFAULT_PORTS.get(self._protocol, None)
        self._host = url_data.hostname

        if not self._protocol or not self._port or not self._host:
            raise InventorySourceError('netbox: invalid url provided')

        self._tag = input_data.get('tag', 'null')
        self._namespace = input_data.get('namespace', 'site.name')
        self._period = input_data.get('period', 3600)
        self._run_once = input_data.get('run_once', False)
        self._token = input_data.get('token', None)
        self._auth = input_data.get('auth', None)
        self._device = input_data.get('device', None)

    def _validate_config(self, input_data) -> list:
        """Validates the loaded configuration

        Returns:
            list: the list of errors
        """
        errors = []
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

    async def retrieve_rest_data(self, url: str) -> Dict:
        """Perform an HTTP GET to the <url> parameter.

        Args:
            url (str): HTTP GET target

        Raises:
            RuntimeError: Unable to connect to the REST server

        Returns:
            Dict: content of the HTTP GET
        """
        headers = self._token_auth_header()
        if not self._session:
            self._init_session(headers)

        # TODO: check if headers are needed also in .get
        async with self._session.get(url, headers=headers) as response:
            if int(response.status) == 200:
                res = await response.json()

                data = res.get('results', [])

                if res.get('next', None):
                    next_data = self.retrieve_rest_data(res['next'])
                    data.extend(next_data.get('results', []))

                res['results'] = data
                res['next'] = None
                return res
            else:
                raise RuntimeError(
                    'Unable to connect to netbox:', response.json())

    def parse_inventory(self, raw_inventory: dict) -> List[Dict]:
        """parse the raw inventory collected from the server and generates
           a new inventory with only the required informations

        Args:
            raw_inventory (dict): raw inventory received from the server

        Returns:
            List[Dict]: a list containing the inventory
        """
        def get_field_value(entry, fields_str):
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

        inventory_list = raw_inventory.get('results', [])
        inventory = {}

        for device in inventory_list:
            inventory[device['name']] = {}
            for rel_field in _RELEVANT_FIELDS:
                if rel_field == 'name':
                    inventory[device['name']]['hostname'] = \
                        get_field_value(device, rel_field)
                elif rel_field == 'primary_ip6.address':
                    inventory[device['name']]['ipv6'] = \
                        get_field_value(device, rel_field)
                elif rel_field == 'primary_ip4.address':
                    inventory[device['name']]['ipv4'] = \
                        get_field_value(device, rel_field)

            if inventory[device['name']]['ipv4']:
                inventory[device['name']
                          ]['address'] = inventory[device['name']]['ipv4']
            elif inventory[device['name']]['ipv6']:
                inventory[device['name']
                          ]['address'] = inventory[device['name']]['ipv6']

            inventory[device['name']]['devtype'] = self._device.get('devtype')

            # only ssh supported for now
            inventory[device['name']]['transport'] = self._device.get(
                'transport') or 'ssh'
            inventory[device['name']]['port'] = 22

            if self._namespace == 'site.name'\
                    and 'site.name' in _RELEVANT_FIELDS:
                inventory[device['name']]['namespace'] = \
                    inventory[device['name']].get('site.name', '')
            else:
                inventory[device['name']]['namespace'] = self._namespace

        return list(inventory.values())

    async def _execute(self):
        while True:
            # Retrieve data using REST
            url = f'{self._protocol}://{self._host}:{self._port}'\
                f'/api/dcim/devices/?tag={self._tag}'
            raw_inventory = await self.retrieve_rest_data(url)
            logger.debug(f"Received netbox inventory from {url}")
            tmp_inventory = self.parse_inventory(raw_inventory)
            # load credentials into the inventory
            self._auth.load(tmp_inventory)

            # Write the inventory and remove the tmp one

            self.set_inventory(tmp_inventory)

            if self._run_once:
                break

            await asyncio.sleep(self._period)

    async def _stop(self):
        if self._session:
            await self._session.close()
