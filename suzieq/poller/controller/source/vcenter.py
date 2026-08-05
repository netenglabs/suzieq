"""Vcenter module

This module contains the methods to connect to a Vcenter server to
retrieve the list of VMs.
"""

import asyncio
import logging
import ssl
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator
from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim, vmodl

from suzieq.poller.controller.inventory_async_plugin import \
    InventoryAsyncPlugin
from suzieq.poller.controller.source.base_source import Source, SourceModel
from suzieq.shared.exceptions import InventorySourceError, SensitiveLoadError
from suzieq.shared.utils import get_sensitive_data

_DEFAULT_PORTS = {'https': 443}

logger = logging.getLogger(__name__)


class VcenterServerModel(BaseModel, extra='forbid'):
    """Model containing data to connect with vcenter server."""
    host: str
    port: int


class VcenterSourceModel(SourceModel):
    """Vcenter source validation model."""
    username: str
    password: str
    attributes: Optional[List] = Field(default_factory=lambda: ['suzieq'])
    period: Optional[int] = Field(default=3600)
    ssl_verify: Optional[bool] = Field(default=None, alias='ssl-verify')
    server: Union[str, VcenterServerModel] = Field(alias='url')
    run_once: Optional[bool] = Field(default=False, alias='run_once')

    @model_validator(mode='before')
    @classmethod
    def validate_and_set(cls, data):
        """Validate the field 'url' and set the correct parameters
        """
        if not isinstance(data, dict):
            return data
        url = data.get('url')
        if isinstance(url, str):
            url_data = urlparse(url)
            host = url_data.hostname
            if not host:
                raise ValueError(f'Unable to parse hostname {url}')
            port = url_data.port or _DEFAULT_PORTS.get("https")
            if not port:
                raise ValueError(f'Unable to parse port {url}')
            server = VcenterServerModel(host=host, port=port)
            ssl_verify = data.get('ssl-verify')
            if ssl_verify is None:
                ssl_verify = True
            data['ssl-verify'] = ssl_verify
            data['url'] = server
            return data
        elif isinstance(url, VcenterServerModel):
            return data
        else:
            raise ValueError('Unknown input type')

    @field_validator('password')
    @classmethod
    def validate_password(cls, password):
        """checks if the password can be load as sensible data
        """
        try:
            if password == 'ask':
                return password
            return get_sensitive_data(password)
        except SensitiveLoadError as e:
            raise ValueError(e)


class Vcenter(Source, InventoryAsyncPlugin):
    """This class is used to dynamically retrieve the inventory
    from Vcenter
    """
    def __init__(self, config_data: dict, validate: bool = True) -> None:
        self._status = 'init'
        self._server: VcenterServerModel = None
        self._session = None

        super().__init__(config_data, validate)

    @classmethod
    def get_data_model(cls):
        return VcenterSourceModel

    def _load(self, input_data):
        # load the server class from the dictionary
        if not self._validate:
            input_data['server'] = VcenterServerModel.model_construct(
                **input_data.pop('url', {}))
            input_data['ssl_verify'] = input_data.pop('ssl-verify', False)
        super()._load(input_data)
        if self._data.password == 'ask':
            self._data.password = get_sensitive_data(
                'ask', f'{self.name} Insert vcenter password: '
            )
        self._server = self._data.server
        if not self._auth:
            raise InventorySourceError(
                f"{self.name} Vcenter must have an "
                "'auth' set in the 'namespaces' section")

    def _init_session(self):
        """Initialize the session property"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        if not self._data.ssl_verify:
            context.verify_mode = ssl.CERT_NONE

        try:
            self._session = SmartConnect(
                host=self._server.host,
                port=self._server.port,
                user=self._data.username,
                pwd=self._data.password,
                sslContext=context
            )
        except Exception as e:
            self._session = None
            raise InventorySourceError(
                f"Failed to connect to VCenter: {str(e)}")

    def _get_custom_keys(self, content, attribute_names):
        """Retrieve custom attribute keys based on their names."""
        all_custom_fields = {field.name: field.key
                             for field in content.customFieldsManager.field}
        return [
            all_custom_fields[name]
            for name in attribute_names
            if name in all_custom_fields
        ]

    def _create_filter_spec(self, view):
        """Return a FilterSpec based on provided view and attribute keys."""
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name='traverseEntities', path='view', skip=False,
            type=vim.view.ContainerView,
            selectSet=[vmodl.query.PropertyCollector.SelectionSpec(
                name='traverseEntities')])
        prop_set = vmodl.query.PropertyCollector.PropertySpec(
            all=False, type=vim.VirtualMachine)
        prop_set.pathSet = ['name', 'guest.ipAddress', 'customValue']
        obj_spec = vmodl.query.PropertyCollector.ObjectSpec(
            obj=view, selectSet=[traversal_spec])
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = [obj_spec]
        filter_spec.propSet = [prop_set]
        return filter_spec

    async def get_inventory_list(self) -> List:
        """
        Retrieve VMs that have any specified custom attribute names.

        This method uses vSphere's Property Collector to fetch only
        properties that are required. This is a lot faster than
        fetching the entire inventory and filtering on attributes.
        """
        if not self._session:
            self._init_session()

        content = self._session.RetrieveContent()
        view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True)
        attribute_keys = self._get_custom_keys(content, self._data.attributes)

        filter_spec = self._create_filter_spec(view)
        retrieve_options = vmodl.query.PropertyCollector.RetrieveOptions()
        result = content.propertyCollector.RetrievePropertiesEx(
            [filter_spec], retrieve_options)
        vms_with_ip = {}
        while result:
            for obj in result.objects:
                vm_name = None
                vm_ip = None
                has_custom_attr = False
                for prop in obj.propSet:
                    if prop.name == 'name':
                        vm_name = prop.val
                    elif prop.name == 'guest.ipAddress' and prop.val:
                        vm_ip = prop.val
                    elif prop.name == 'customValue':
                        has_custom_attr = any(
                            cv.key in attribute_keys for cv in prop.val)
                if has_custom_attr and vm_ip:
                    vms_with_ip[vm_name] = vm_ip

            if hasattr(result, 'token') and result.token:
                property_collector = content.propertyCollector
                result = property_collector.ContinueRetrievePropertiesEx(
                    token=result.token)
            else:
                break

        view.Destroy()
        logger.info(
            f'Vcenter: Retrieved {len(vms_with_ip)} VMs with IPs')
        return vms_with_ip

    def parse_inventory(self, inventory_list: dict) -> Dict:
        """parse the raw inventory collected from the server and generates
           a new inventory with only the required information.

        Args:
            raw_inventory: raw inventory received from vcenter.

        Returns: A dict containing the inventory.
        """
        inventory = {}
        for name, ip in inventory_list.items():
            namespace = self._namespace
            inventory[f'{namespace}.{ip}'] = {
                'address': ip,
                'namespace': namespace,
                'hostname': name,
            }
        logger.info(
            f'Vcenter: Acting on inventory of {len(inventory)} devices')
        return inventory

    async def _execute(self):
        while True:
            inventory_list = await self.get_inventory_list()
            tmp_inventory = self.parse_inventory(inventory_list)
            self.set_inventory(tmp_inventory)
            if self._run_once:
                break
            await asyncio.sleep(self._data.period)

    async def _stop(self):
        if self._session:
            Disconnect(self._session)
