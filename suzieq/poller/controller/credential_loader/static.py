# pylint: disable=no-self-argument
from typing import Dict, Optional

from pydantic import Field, validator

from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader, CredentialLoaderModel, check_credentials
from suzieq.poller.controller.utils.inventory_utils import get_sensitive_data
from suzieq.shared.exceptions import InventorySourceError


class StaticModel(CredentialLoaderModel):
    """Model for static credential loader
    """
    username: Optional[str]
    password: Optional[str]
    ssh_passphrase: Optional[str] = Field(alias='ssh-passphrase')
    keyfile: Optional[str]

    @validator('password', 'ssh_passphrase')
    def validate_sens_field(cls, field):
        """Validate if the sensitive var was passed correctly
        """
        try:
            if field == 'ask':
                # the field is valid, but I cannot ask here the value
                return field
            return get_sensitive_data(field)
        except InventorySourceError as e:
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
            init_data['ssh_passphrase'] = init_data.pop('ssh-passphrase', None)
        super().init(init_data)

        if self._data.password == 'ask':
            try:
                self._data.password = get_sensitive_data(
                    self._data.password,
                    f'{self.name} Password to login to device: ')
            except InventorySourceError as e:
                raise InventorySourceError(f'{self.name} {e}')

        if self._data.ssh_passphrase == 'ask':
            try:
                self._data.ssh_passphrase = get_sensitive_data(
                    self._data.ssh_passphrase,
                    f'{self.name} Passphrase to decode private key file: '
                )
            except InventorySourceError as e:
                raise InventorySourceError(f'{self.name} {e}')

    def load(self, inventory: Dict[str, Dict]):

        for device in inventory.values():
            dev_creds = {
                'ssh_keyfile': device.get('ssh_keyfile') or self._data.keyfile,
                'password': device.get('password') or self._data.password,
                'username': device.get('username') or self._data.username,
                'passphrase': device.get('passphrase')
                or self._data.ssh_passphrase
            }

            self.write_credentials(device, dev_creds)

        check_credentials(inventory)
