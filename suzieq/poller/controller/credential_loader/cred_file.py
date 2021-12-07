"""This module contains the class to import device credentials using files
"""
from os import path
import yaml
from suzieq.poller.controller.credential_loader \
    .credential_loader import CredentialLoader


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

    def load(self, inventory: dict):

        if not inventory:
            raise RuntimeError("Empty inventory")

        if not self._raw_credentials.get("namespace", None):
            raise RuntimeError(
                "The credentials file must contain all device \
                credential divided in namespaces"
            )

        for ns_credentials in self._raw_credentials["namespace"]:
            namespace = ns_credentials.get("name", "")
            if not namespace:
                raise RuntimeError("All namespaces must have a name")

            ns_devices = ns_credentials.get("devices", [])
            if not ns_devices:
                raise RuntimeError("No devices in {} namespace"
                                   .format(namespace))

            for dev_info in ns_devices:
                dev_name = dev_info.get("name", "")
                if not dev_name:
                    raise RuntimeError("Devices must have a name")

                if dev_name not in inventory:
                    raise RuntimeError("Unknown device called {}"
                                       .format(dev_name))

                if namespace != inventory.get(dev_name, {})\
                        .get("namespace", ""):
                    raise RuntimeError(
                        "The device {} does not belong the namespace {}"
                        .format(dev_name, namespace)
                    )

                dev_cred = dev_info.get("credentials", None)
                if not dev_cred:
                    raise RuntimeError("Device must contains credentials")

                dev_cred["options"] = dev_info.get("options", {})

                self.write_credentials(inventory[dev_name], dev_cred)

                # inventory[dev_name]["credentials"] = dev_cred
                # inventory[dev_name]["credentials"]["options"] = dev_info\
                #     .get("options", {})

        # check if all devices has credentials
        no_cred_devs = [
            k for (k, d) in inventory.items()
            if not d.get("username", None)
        ]
        if len(no_cred_devs) != 0:
            raise RuntimeError(
                "Some devices are left without credentials: {}"
                .format(no_cred_devs)
            )
