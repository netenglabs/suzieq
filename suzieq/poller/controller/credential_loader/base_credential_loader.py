"""This module contains the base class for plugins which loads
devices credentials
"""
from abc import abstractmethod
from typing import Dict, List, Type
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin


class CredentialLoader(ControllerPlugin):
    """Base class used to import device credentials from different
    sources
    """

    def __init__(self, init_data) -> None:
        super().__init__()

        self._cred_format = [
            'username',
            'password',
            'ssh_keyfile'
        ]

        self.init(init_data)

    @abstractmethod
    def init(self, init_data: Type):
        """Initialize the object

        Args:
            init_data (Type): data used to initialize the object
        """

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
            ValueError: Invalid credentials
        """
        missing_keys = self._validate_credentials(credentials)
        if missing_keys:
            raise ValueError(
                f'Invalid credentials: missing keys {missing_keys}')
        device.update(credentials)

    def _validate_credentials(self, device: Dict) -> List[str]:

        cred_keys = set(self._cred_format)
        for key in device.keys():
            if key in cred_keys:
                cred_keys.remove(key)
            else:
                raise RuntimeError(f'Unexpected key {key} in credentials')

        # One between password or ssh_keyfile must be defines
        if 'password' in cred_keys and 'keyfile' in cred_keys:
            cred_keys.remove('password')
            cred_keys.remove('ssh_keyfile')
            ret = list(cred_keys)
            ret.append('password or ssh_keyfile')
            return ret

        if 'password' in cred_keys:
            cred_keys.remove('password')

        if 'ssh_keyfile' in cred_keys:
            cred_keys.remove('ssh_keyfile')

        return list(cred_keys)
