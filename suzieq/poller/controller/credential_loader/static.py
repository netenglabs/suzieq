from typing import Dict, Optional

from pydantic import Field, field_validator

from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader, CredentialLoaderModel, check_credentials
from suzieq.shared.exceptions import SensitiveLoadError, InventorySourceError
from suzieq.shared.utils import get_sensitive_data


class StaticModel(CredentialLoaderModel):
    """Model for static credential loader
    """
    username: Optional[str] = None
    password: Optional[str] = None
    key_passphrase: Optional[str] = Field(default=None, alias='key-passphrase')
    keyfile: Optional[str] = None
    enable_password: Optional[str] = Field(default=None,
                                           alias='enable-password')
    api_key: Optional[str] = Field(default=None, alias='api-key')

    @field_validator('username', 'password', 'key_passphrase',
                     'enable_password', 'api_key')
    @classmethod
    def validate_sens_field(cls, value):
        """Validate if the sensitive var was passed correctly
        """
        try:
            if value == 'ask':
                # the field is valid, but I cannot ask here the value
                return value
            return get_sensitive_data(value)
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
            init_data['api_key'] = init_data.pop('api-key', None)
        super().init(init_data)

        if self._data.username == 'ask':
            try:
                self._data.username = get_sensitive_data(
                    self._data.username,
                    f'{self.name} Username to login to device: ')
            except SensitiveLoadError as e:
                raise InventorySourceError(f'{self.name} {e}')

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

        if self._data.api_key == 'ask':
            try:
                self._data.api_key = get_sensitive_data(
                    self._data.api_key, f'{self.name} Insert API key: ')
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
                'enable_password': self._data.enable_password,
            }
            if self._data.api_key and not device.get('api_key'):
                dev_creds['api_key'] = self._data.api_key

            self.write_credentials(device, dev_creds)

        check_credentials(inventory)
