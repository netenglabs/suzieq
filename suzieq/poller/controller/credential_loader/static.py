# pylint: disable=no-self-argument
from typing import Dict, Optional

from pydantic import Field, validator

from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader, CredentialLoaderModel, check_credentials
from suzieq.shared.utils import get_sensitive_data
from suzieq.shared.exceptions import SensitiveLoadError, InventorySourceError


class StaticModel(CredentialLoaderModel):
    """Model for static credential loader
    """
    username: Optional[str]
    password: Optional[str]
    key_passphrase: Optional[str] = Field(alias='key-passphrase')
    keyfile: Optional[str]
    enable_password: Optional[str] = Field(alias='enable-password')

    @validator('password', 'key_passphrase', 'enable_password')
    def validate_sens_field(cls, field):
        """Validate if the sensitive var was passed correctly
        """
        try:
            if field == 'ask':
                # the field is valid, but I cannot ask here the value
                return field
            return get_sensitive_data(field)
        except SensitiveLoadError as e:
            raise ValueError(e)


class StaticLoader(CredentialLoader):
    """Simple credential loader

    Loads the credentials inside all devices
    """

    @classmethod
    def get_data_model(cls):
        return StaticModel

    def init(self, init_data: dict):
        """Initialize parameters common to all devices

        Args:
            init_data (Dict): configuration dictionary

        Raises:
            InventorySourceError: Invalid env argument
        """
        if not self._validate:
            # fix pydantic alias
            init_data['enable_password'] = \
                init_data.pop('enable-password', None)
            init_data['key_passphrase'] = init_data.pop('key-passphrase', None)
        super().init(init_data)

        if self._data.password == 'ask':
            try:
                self._data.password = get_sensitive_data(
                    self._data.password,
                    f'{self.name} Password to login to device: ')
            except SensitiveLoadError as e:
                raise InventorySourceError(f'{self.name} {e}')

        if self._data.enable_password == 'ask':
            try:
                self._data.enable_password = get_sensitive_data(
                    self._data.enable_password,
                    f'{self.name} Insert enable password: '
                )
            except SensitiveLoadError as e:
                raise InventorySourceError(f'{self.name} {e}')

        if self._data.key_passphrase == 'ask':
            try:
                self._data.key_passphrase = get_sensitive_data(
                    self._data.key_passphrase,
                    f'{self.name} Passphrase to decode private key file: '
                )
            except SensitiveLoadError as e:
                raise InventorySourceError(f'{self.name} {e}')

    def load(self, inventory: Dict[str, Dict]):

        for device in inventory.values():
            dev_creds = {
                'ssh_keyfile': device.get('ssh_keyfile') or self._data.keyfile,
                'password': device.get('password') or self._data.password,
                'username': device.get('username') or self._data.username,
                'passphrase': device.get('passphrase')
                or self._data.key_passphrase,
                'enable_password': self._data.enable_password
            }

            self.write_credentials(device, dev_creds)

        check_credentials(inventory)
