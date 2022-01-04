import getpass
from os import getenv
from typing import Dict

from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader
from suzieq.shared.exceptions import InventorySourceError


class StaticLoader(CredentialLoader):
    """Simple credential loader

    Loads the credentials inside all devices
    """

    def __init__(self, init_data: Dict) -> None:
        self._password = None
        self._passphrase = None
        self._keyfile = None
        self._username = None
        super().__init__(init_data)

    def _validate_config(self, config: Dict):
        self._valid_fields.extend(['username', 'password',
                                   'ssh-passphrase', 'keyfile'])
        return super()._validate_config(config)

    def init(self, init_data: dict):
        """Initialize parameters common to all devices

        Args:
            init_data (Dict): configuration dictionary

        Raises:
            InventorySourceError: Invalid env argument
        """
        self._username = init_data.get('username')

        if init_data.get('keyfile'):
            self._keyfile = init_data['keyfile']

        if init_data.get('password'):
            password = init_data['password']
            if password.startswith('env:'):
                self._password = getenv(password.split('env:')[1], '')
                if not self._password:
                    raise InventorySourceError(
                        f'No password in environment '
                        f'variable "{password.split("env:")[1]}"')
            elif password.startswith('plain:'):
                self._password = password.split("plain:")[1]
            elif password.startswith('ask'):
                self._password = getpass.getpass(
                    f'{self._name} Password to login to device: ')
            else:
                raise InventorySourceError(
                    f'{self._name} unknown password method.'
                    'Supported methods are ["ask", "plain:", "env:"]')

        if init_data.get('ssh-passphrase'):
            passphrase = init_data['ssh-passphrase']
            if passphrase.startswith('env:'):
                self._passphrase = getenv(
                    passphrase.split('env:')[1], '')
                if not self._passphrase:
                    raise InventorySourceError(
                        f'No passphrase in environment '
                        f'variable "{passphrase.split("env:")[1]}"')
            elif passphrase.startswith('plain:'):
                self._passphrase = passphrase.split("plain:")[1]
            elif passphrase.startswith('ask'):
                self._passphrase = getpass.getpass(
                    f'{self._name} Passphrase to decode private key file: '
                )

    def load(self, inventory: Dict[str, Dict]):

        for device in inventory.values():
            dev_creds = {
                'ssh_keyfile': device.get('ssh_keyfile') or self._keyfile,
                'password': device.get('password') or self._password,
                'username': device.get('username') or self._username,
                'passphrase': device.get('passphrase') or self._passphrase
            }

            self.write_credentials(device, dev_creds)
