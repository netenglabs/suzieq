"""Nautobot inventory"""

import asyncio
import logging
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse

from pynautobot import api

from suzieq.poller.controller.source.base_source import Source, SourceModel
from suzieq.poller.controller.inventory_async_plugin import InventoryAsyncPlugin
from suzieq.shared.utils import get_sensitive_data
from suzieq.shared.exceptions import InventorySourceError, SensitiveLoadError

# pylint: disable=no-name-in-module
# pylint: disable=no-self-argument

from pydantic import BaseModel, validator, Field

logger = logging.getLogger(__name__)

_DEFAULT_PORTS = {"http": 80, "https": 443}


class NautobotServerModel(BaseModel):
    """Model containing data to connect with Nautobot server"""

    host: str
    protocol: str
    port: str

    class Config:
        """pydantic configuration"""

        extra = "forbid"


class NautobotSourceModel(SourceModel):
    """Nautobot source validation model"""

    period: Optional[int] = Field(default=3600)
    token: str
    ssl_verify: Optional[bool] = Field(alias="ssl-verify")
    server: Union[str, NautobotServerModel] = Field(alias="url")
    run_once: Optional[bool] = Field(default=False, alias="run_once")
    device_filters: Optional[Dict] = Field(default=None, alias="device_filters")

    @validator("server", pre=True)
    def validate_and_set(cls, url, values):
        """Validate the field 'url' and set the correct parameters"""
        if isinstance(url, str):
            url_data = urlparse(url)
            host = url_data.hostname
            if not host:
                raise ValueError(f"Unable to parse hostname {url}")
            protocol = url_data.scheme or "http"
            if protocol not in _DEFAULT_PORTS:
                raise ValueError(f"Unknown protocol {protocol}")
            port = url_data.port or _DEFAULT_PORTS.get(protocol)
            if not port:
                raise ValueError(f"Unable to parse port {url}")
            server = NautobotServerModel(host=host, port=port, protocol=protocol)
            ssl_verify = values["ssl_verify"]
            if ssl_verify is None:
                if server.protocol == "http":
                    ssl_verify = False
                else:
                    ssl_verify = True
            else:
                if server.protocol == "http" and ssl_verify:
                    raise ValueError("Cannot use ssl_verify=True with http host")
            values["ssl_verify"] = ssl_verify
            return server
        elif isinstance(url, NautobotServerModel):
            return url
        else:
            raise ValueError("Unknown input type")

    @validator("token")
    def validate_token(cls, token):
        """checks if the token can be load as sensible data"""
        try:
            if token == "ask":
                return token
            return get_sensitive_data(token)
        except SensitiveLoadError as e:
            raise ValueError(e)


class Nautobot(Source, InventoryAsyncPlugin):
    """This class is used to dynamically retrieve the inventory from Nautobot"""

    def __init__(self, config_data: dict, validate: bool = True) -> None:
        self._status = "init"
        self._session: api = None
        self._server: NautobotServerModel = None
        super().__init__(config_data, validate)

    @classmethod
    def get_data_model(cls):
        return NautobotSourceModel

    def _load(self, input_data):
        # load the server class from the dictionary
        if not self._validate:
            input_data["server"] = NautobotServerModel.construct(
                **input_data.pop("url", {})
            )
            input_data["ssl_verify"] = input_data.pop("ssl-verify", False)
        super()._load(input_data)
        if self._data.token == "ask":
            self._data.token = get_sensitive_data(
                "ask", f"{self.name} Insert Nautobot API token: "
            )
        self._server = self._data.server
        if not self._auth:
            raise InventorySourceError(
                f"{self.name} Nautobot must have an "
                "'auth' set in the 'namespaces' section"
            )

    def _init_session(self):
        """Initialize the session property

        Args:
            headers ([dict]): headers to initialize the session
        """
        url_address = (
            f"{self._server.protocol}://{self._server.host}:" f"{self._server.port}"
        )

        if not self._session:
            ssl_option = self._data.ssl_verify
            self._session = api(
                url=url_address, token=self._data.token, verify=ssl_option
            )

    async def get_inventory_list(self) -> List:
        """Contact Nautobot to retrieve the inventory.

        Raises:
            InventorySourceError: Unable to connect to the REST server

        Returns:
            List: inventory list
        """

        if not self._session:
            self._init_session()
        try:
            if self._data.device_filters:
                devices = self._session.dcim.devices.filter(**self._data.device_filters)
            else:
                devices = self._session.dcim.devices.all()
        except Exception as e:
            raise InventorySourceError(
                f"{self.name}: error while " f"getting devices: {e}"
            )

        logger.info(f"Nautobot: Retrieved inventory list of {len(devices)} devices")
        return devices

    def parse_inventory(self, inventory_list: list) -> Dict:
        """parse the raw inventory collected from the server and generates
           a new inventory with only the required informations

        Args:
            raw_inventory (list): raw inventory received from the server

        Returns:
            List[Dict]: a list containing the inventory
        """
        inventory = {}
        ignored_device_count = 0

        for device in inventory_list:
            ipv4 = device.primary_ip4.address if device.primary_ip4 else None
            ipv6 = device.primary_ip6.address if device.primary_ip6 else None
            hostname = device.name
            site_name = device.location.name
            if self._namespace == "group-by-location":
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
                    f"Skipping {namespace}.{hostname}: doesn't have a management IP"
                )
                ignored_device_count += 1
                continue

            address = address.split("/")[0]

            inventory[f"{namespace}.{address}"] = {
                "address": address,
                "namespace": namespace,
                "hostname": hostname,
            }

        logger.info(
            f"Nautobot: Acting on inventory of {len(inventory)} devices, "
            f"ignoring {ignored_device_count} devices"
        )

        return inventory

    async def _execute(self):
        while True:
            inventory_list = await self.get_inventory_list()
            logger.debug(
                f"Received Nautobot inventory from {self._server.protocol}"
                f"://{self._server.host}:{self._server.port}"
            )
            tmp_inventory = self.parse_inventory(inventory_list)
            # Write the inventory and remove the tmp one
            self.set_inventory(tmp_inventory)

            if self._run_once:
                break

            await asyncio.sleep(self._data.period)
