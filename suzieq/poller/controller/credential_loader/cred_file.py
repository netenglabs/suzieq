"""This module contains the class to import device credentials using files
"""
from os import path
from typing import Dict

import yaml
from suzieq.poller.controller.credential_loader.base_credential_loader import \
    CredentialLoader


class CredFile(CredentialLoader):
    """Reads devices credentials from a file and write them on the inventory
    """

    def init(self, init_data: dict):
        dev_cred_file = init_data.get('path', '')
        if not dev_cred_file:
            raise RuntimeError(
                'No field <path>\
                    for device credential provided'
            )
        if not dev_cred_file or not path.isfile(dev_cred_file):
            raise RuntimeError('The credential file ' 'does not exists')
        with open(dev_cred_file, 'r') as f:
            self._raw_credentials = yaml.safe_load(f.read())

        if not isinstance(self._raw_credentials, list):
            raise RuntimeError(
                'The credentials file must contain all device \
                credential divided in namespaces'
            )

    def load(self, inventory: Dict):
        if not inventory:
            raise RuntimeError('Empty inventory')

        for ns_credentials in self._raw_credentials:
            namespace = ns_credentials.get('namespace', '')
            if not namespace:
                raise RuntimeError('All namespaces must have a name')

            ns_devices = ns_credentials.get('devices', [])
            if not ns_devices:
                raise RuntimeError('No devices in {} namespace'
                                   .format(namespace))

            for dev_info in ns_devices:
                if dev_info.get('hostname'):
                    dev_id = dev_info['hostname']
                    dev_key = 'hostname'
                elif dev_info.get('address'):
                    dev_id = dev_info['address']
                    dev_key = 'address'
                else:
                    raise RuntimeError(
                        'Devices must have a hostname or address')

                device = [x for x in inventory.values() if x.get(dev_key)
                          == dev_id]
                if not device:
                    raise RuntimeError('Unknown device called {}'
                                       .format(dev_id))
                device = device[0]
                if namespace != device.get('namespace', ''):
                    raise RuntimeError(
                        'The device {} does not belong the namespace {}'
                        .format(dev_id, namespace)
                    )
                if dev_info.get('keyfile'):
                    # rename 'keyfile' into 'ssh_keyfile'
                    dev_info['ssh_keyfile'] = dev_info.pop('keyfile')

                if 'passphrase' not in dev_info:
                    if dev_info.get('ssh-key-pass'):
                        # rename 'ssh-key-pass' into 'passphrase'
                        dev_info['passphrase'] = dev_info.pop('key-passphrase')
                    else:
                        # set it to None
                        dev_info['passphrase'] = None

                dev_cred = dev_info.copy()

                dev_cred.pop(dev_key)

                if not dev_cred.get('password') and \
                        not dev_cred.get('ssh_keyfile'):
                    # no configuration in device, use config ones
                    dev_cred.update({
                            'passphrase': self._conf_passphrase,
                            'ssh_key_file': self._conf_keyfile,
                            'password': self._conf_password
                        })

                self.write_credentials(device, dev_cred)

        # check if all devices has credentials
        no_cred_devs = [
            f"{d.get('namespace')}.{d.get('address')}"
            for d in inventory.values()
            if not d.get('username', None)
        ]
        if len(no_cred_devs) != 0:
            raise RuntimeError(
                'Some devices are left without credentials: {}'
                .format(no_cred_devs)
            )
