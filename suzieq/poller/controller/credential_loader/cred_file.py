"""This module contains the class to import device credentials using files
"""
from os import path
from typing import Dict, List
import yaml
from suzieq.poller.controller.credential_loader.base_credential_loader \
    import CredentialLoader


class CredFile(CredentialLoader):
    """Reads devices credentials from a file and write them on the inventory
    """
    def init(self, init_data: dict):
        dev_cred_file = init_data.get("file_path", "")
        if not dev_cred_file:
            raise RuntimeError(
                "No field <file_path>\
                    for device credential provided"
            )
        if not dev_cred_file or not path.isfile(dev_cred_file):
            raise RuntimeError("The credential file " "does not exists")
        with open(dev_cred_file, "r") as f:
            self._raw_credentials = yaml.safe_load(f.read())

    def load(self, inventory: List[Dict]):

        if not inventory:
            raise RuntimeError("Empty inventory")

        if not isinstance(self._raw_credentials, list):
            raise RuntimeError(
                "The credentials file must contain all device \
                credential divided in namespaces"
            )

        for ns_credentials in self._raw_credentials:
            namespace = ns_credentials.get("namespace", "")
            if not namespace:
                raise RuntimeError("All namespaces must have a name")

            ns_devices = ns_credentials.get("devices", [])
            if not ns_devices:
                raise RuntimeError("No devices in {} namespace"
                                   .format(namespace))

            for dev_info in ns_devices:
                dev_id = dev_info.get("name", "")
                if not dev_id:
                    raise RuntimeError("Devices must have a name")

                device = [x for x in inventory if x.get("id") == dev_id]
                if not device:
                    raise RuntimeError("Unknown device called {}"
                                       .format(dev_id))
                device = device[0]

                if namespace != device.get("namespace", ""):
                    raise RuntimeError(
                        "The device {} does not belong the namespace {}"
                        .format(dev_id, namespace)
                    )

                dev_cred = dev_info.get("credentials", {})
                if not dev_cred:
                    raise RuntimeError("Device must contains credentials")
                dev_cred["ssh_keyfile"] = dev_cred["keyfile"]
                dev_cred.pop("keyfile")

                dev_cred["options"] = dev_info.get("options") or {}

                self.write_credentials(device, dev_cred)

        # check if all devices has credentials
        no_cred_devs = [
            d.get("id") for d in inventory
            if not d.get("username", None)
        ]
        if len(no_cred_devs) != 0:
            raise RuntimeError(
                "Some devices are left without credentials: {}"
                .format(no_cred_devs)
            )
