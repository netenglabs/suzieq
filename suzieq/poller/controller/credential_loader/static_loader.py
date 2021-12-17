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
                'ssh_keyfile': self._conf_keyfile,
                'password': self._conf_password,
                'ssh_key_pass': self._conf_ssh_key_pass,
                'username': self._conf_username
            }

            self.write_credentials(device, dev_creds)
