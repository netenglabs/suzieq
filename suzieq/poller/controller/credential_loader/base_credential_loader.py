"""This module contains the base class for plugins which loads
devices credentials
"""
import logging
from abc import abstractmethod
from typing import Dict, List

from suzieq.poller.controller.base_controller_plugin import \
    InventoryPluginModel, ControllerPlugin
from suzieq.shared.exceptions import InventorySourceError

logger = logging.getLogger(__name__)


def check_credentials(inventory: Dict):
    """Checks if all the credentials are set
    """

    # check if all devices has credentials
    no_cred_nodes = [
        f"{d.get('namespace')}.{d.get('address')}"
        for d in inventory.values()
        if not d.get('username', None) or
        not (d.get('password') or d.get('ssh_keyfile'))
    ]
    if no_cred_nodes:
        raise InventorySourceError(
            'No credentials to log into the following nodes: '
            f'{no_cred_nodes}'
        )


class CredentialLoaderModel(InventoryPluginModel):
    """Model for credential loader validation
    """


class CredentialLoader(ControllerPlugin):
    """Base class used to import device credentials from different
    sources
    """

    def __init__(self, init_data: Dict, validate: bool = True) -> None:
        super().__init__(init_data, validate)

        self._cred_format = [
            'username',
            'password',
            'ssh_keyfile',
            'passphrase',
            'enable_password'
        ]

        self._optional_cred_keys = [
            'enable_password',
        ]

        self._data: CredentialLoaderModel = None
        self.init(init_data)

    @property
    def name(self) -> str:
        """Name of the source set in the inventory file

        Returns:
            str: name of the source
        """
        return self._data.name

    @classmethod
    def default_type(cls) -> str:
        return 'static'

    @classmethod
    def get_data_model(cls):
        return CredentialLoaderModel

    def init(self, init_data: Dict):
        """Initialize the object

        Args:
            init_data (Dict): data used to initialize the object
        """
        if self._validate:
            self._data = self.get_data_model()(**init_data)
        else:
            self._data = self.get_data_model().construct(**init_data)
        if not self._data:
            raise InventorySourceError(
                'input_data was not loaded correctly')

    @abstractmethod
    def load(self, inventory: Dict[str, Dict]):
        """Loads the credentials inside the inventory

        Args:
            inventory (Dict[str, Dict]): inventory to update
        """

    def write_credentials(self, device: Dict, credentials: Dict[str, Dict]):
        """write and validate input credentials for a device

        Args:
            device (Dict): device to add credentials
            credentials (Dict[str, Dict]): device's credentials

        Raises:
            InventorySourceError: Invalid credentials
        """
        missing_keys = self._validate_credentials(credentials)
        if missing_keys:
            raise InventorySourceError(
                f'Invalid credentials: missing keys {missing_keys}')
        device.update(credentials)

    def _validate_credentials(self, credentials: Dict) -> List[str]:
        """Checks if provided credentials are valid

        Args:
            credentials (Dict): device credentials

        Raises:
            RuntimeError: Unexpected key

        Returns:
            List[str]: list of missing fields
        """
        cred_keys = set(self._cred_format)
        for key, value in credentials.items():
            if key in cred_keys:
                # 'passphrase' is valid also with None value
                # Also 'password' and 'ssh_keyfile' with None value are valid
                # but only if at least one of them has a not None value
                if value or key == 'passphrase':
                    cred_keys.remove(key)
            else:
                raise InventorySourceError(
                    f'Unexpected key {key} in credentials')

        # One between password or ssh_keyfile must be defines
        if 'password' in cred_keys and 'ssh_keyfile' in cred_keys:
            cred_keys.remove('password')
            cred_keys.remove('ssh_keyfile')
            ret = list(cred_keys)
            ret.append('password or ssh_keyfile')
            return ret

        # if we arrived at this point, password or ssh_keyfile
        # is set. Remove the not set one
        if 'password' in cred_keys:
            cred_keys.remove('password')

        if 'ssh_keyfile' in cred_keys:
            cred_keys.remove('ssh_keyfile')

        cred_keys = [x for x in cred_keys
                     if x not in self._optional_cred_keys]
        return list(cred_keys)
