from typing import Dict
from suzieq.poller.controller.credential_loader.base_credential_loader \
    import CredentialLoader


class StaticLoader(CredentialLoader):
    """Simple credential loader

    Loads the credentials inside all devices
    """

    def init(self, init_data: dict):
        pass

    def load(self, inventory: Dict[str, Dict]):

        for device in inventory.values():
            dev_creds = {
                'ssh_keyfile': device.get('ssh_keyfile') or self._conf_keyfile,
                'password': device.get('password') or self._conf_password,
                'username': device.get('username') or self._conf_username,
                'passphrase': device.get('passphrase') or self._conf_passphrase
            }

            self.write_credentials(device, dev_creds)
