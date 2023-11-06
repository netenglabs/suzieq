# pylint: disable=no-name-in-module

from typing import Dict, List, Optional
from urllib3.util import parse_url
from pydantic import BaseModel, Field, validator

from suzieq.shared.utils import PollerTransport


class InventoryModel(BaseModel):
    """Model for the inventory validation
    """
    sources: List[Dict] = Field(min_items=1)
    namespaces: List[Dict] = Field(min_items=1)
    auths: Optional[List[Dict]]
    devices: Optional[List[Dict]]

    class Config:
        """pydantic configuration
        """
        extra = 'forbid'


class DeviceModel(BaseModel):
    """Device model validation
    """
    name: str
    jump_host: Optional[str] = Field(alias='jump-host')
    jump_host_key_file: Optional[str] = Field(alias='jump-host-key-file')
    ignore_known_hosts: Optional[bool] = Field(
        alias='ignore-known-hosts', default=False)
    slow_host: Optional[bool] = Field(alias='slow-host', default=False)
    per_cmd_auth: Optional[bool] = Field(alias='per-cmd-auth', default=True)
    retries_on_auth_fail: Optional[int] = Field(alias='retries-on-auth-fail',
                                                default=1)
    transport: Optional[PollerTransport]
    port: Optional[int]
    devtype: Optional[str]

    # pylint: disable=no-self-argument
    @validator('jump_host')
    def jump_host_validator(cls, value):
        '''Validate jump host format'''
        try:
            uri = parse_url(value)
            assert uri.scheme is None, \
                'format username@jumphost[:port] required'
            return value
        except ValueError:
            assert False, f'Invalid jumphost format: {value}'

    class Config:
        """pydantic configuration
        """
        extra = 'forbid'


class NamespaceModel(BaseModel):
    """Namespace model validation
    """
    name: str
    source: str
    device: Optional[str]
    auth: Optional[str]

    class Config:
        """pydantic configuration
        """
        extra = 'forbid'
