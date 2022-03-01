"""This module contains the class to import device credentials using files
"""
# pylint: disable=no-name-in-module
# pylint: disable=no-self-argument
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator

import yaml
from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader, CredentialLoaderModel, check_credentials
from suzieq.shared.exceptions import InventorySourceError

logger = logging.getLogger(__name__)


class CredFileEntryModel(BaseModel):
    """Model to validate entries in credential file
    """
    hostname: Optional[str]
    address: Optional[str]
    username: Optional[str]
    password: Optional[str]
    keyfile: Optional[str]
    key_passphrase: Optional[str] = Field(alias='key-passphrase')
    enable_password: Optional[str] = Field(alias='enable-password')

    class Config:
        """pydantic configuration
        """
        extra = 'forbid'


class CredFileNamespaceModel(BaseModel):
    """Model to validate the content of the credential file
    """
    namespace: str
    devices: List[CredFileEntryModel]

    class Config:
        """pydantic configuration
        """
        extra = 'forbid'


class CredFileModel(CredentialLoaderModel):
    """Model for credential file validation
    """
    credentials: Union[str, List[CredFileNamespaceModel]] = Field(alias='path')

    @validator('credentials')
    def validate_credentials(cls, cred):
        """validate the credentials
        """
        if isinstance(cred, str):
            dev_cred_file = Path(cred)
            if not dev_cred_file.is_file():
                raise ValueError(
                    f'The credential file {cred} does not exists')

            try:
                with open(dev_cred_file, 'r') as f:
                    credentials = yaml.safe_load(f.read())
            except yaml.YAMLError:
                raise ValueError(
                    'The credential file is not a valid yaml file'
                )

            if not credentials:
                raise ValueError(
                    'The credential file is empty'
                )

            if not isinstance(credentials, list):
                raise ValueError(
                    'The credentials file must contain all device '
                    'credential divided in namespaces'
                )
        elif isinstance(cred, list):
            credentials = cred
        valid_creds = []
        for c in credentials:
            if not isinstance(c, dict):
                raise ValueError(
                    'Namespaces credentials must be a dictionary')
            valid_creds.append(CredFileNamespaceModel(**c))
        return valid_creds


class CredFile(CredentialLoader):
    """Reads devices credentials from a file and write them on the inventory
    """

    @classmethod
    def get_data_model(cls):
        return CredFileModel

    def init(self, init_data: dict):
        if not self._validate:
            # fix pydantic aliases
            init_data['credentials'] = []
            for ns_cred in init_data.pop('path', []):
                init_data['credentials'].append(
                    CredFileNamespaceModel(**ns_cred)
                )

        super().init(init_data)
        if not self._data.credentials:
            raise InventorySourceError(f'{self.name} empty credentials')

    def load(self, inventory: Dict):

        for ns_credentials in self._data.credentials:
            namespace = ns_credentials.namespace
            if not namespace:
                raise InventorySourceError(
                    f'{self.name} All namespaces must have a name')

            ns_nodes = ns_credentials.devices
            if not ns_nodes:
                logger.warning(
                    f'{self.name} No devices in {namespace} namespace')
                continue

            for ns_node in ns_nodes:
                node_info = ns_node.dict(by_alias=True)
                if node_info.get('hostname'):
                    node_id = node_info['hostname']
                    node_key = 'hostname'
                elif node_info.get('address'):
                    node_id = node_info['address']
                    node_key = 'address'
                else:
                    raise InventorySourceError(
                        f'{self.name} Nodes must have a hostname or '
                        'address')

                node = [x for x in inventory.values()
                        if x.get(node_key) == node_id]
                if not node:
                    logger.warning(
                        f'{self.name} Unknown node called {node_id}')
                    continue

                node = node[0]
                if namespace != node.get('namespace', ''):
                    raise InventorySourceError(
                        f'The device {node_id} does not belong the namespace '
                        f'{namespace}'
                    )
                # rename 'keyfile' into 'ssh_keyfile'
                node_info['ssh_keyfile'] = node_info.pop('keyfile', None)

                # rename 'key-passphrase' into 'passphrase'
                node_info['passphrase'] = node_info.pop(
                        'key-passphrase', None)

                # rename 'enable-password' into 'enable_password'
                node_info['enable_password'] = node_info.pop(
                    'enable-password', None)

                node_cred = node_info.copy()

                node_cred.pop('address')
                node_cred.pop('hostname')

                fields = ['username', 'passphrase', 'ssh_keyfile', 'password']
                multi_defined = []
                for f in fields:
                    if node.get(f) and node_cred.get(f):
                        multi_defined.append(f)
                    elif node.get(f):
                        node_cred[f] = node[f]

                if multi_defined:
                    raise InventorySourceError(
                        f"{self.name} the node {node.get('address')} has the "
                        "following strings defined in multiple places "
                        f"{multi_defined}")

                self.write_credentials(node, node_cred)

        check_credentials(inventory)
