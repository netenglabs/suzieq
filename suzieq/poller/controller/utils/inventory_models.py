# pylint: disable=no-name-in-module

import re
from typing import Dict, List, Optional
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
    transport: Optional[PollerTransport]
    port: Optional[str]
    devtype: Optional[str]

    @validator('jump_host')
    def jump_host_validator(cls, value):
        jump_host = value[2:] if value.startswith('//') else value
        pattern = '([a-zA-Z0-9-.]{1,253})@([a-zA-Z0-9-.]{1,253})'
        assert re.fullmatch(pattern, jump_host), \
               'format username@jumphost required'
        return value

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
