import threading
from suzieq.inventoryProvider.plugins.basePlugins.inventorySource \
    import InventorySource
from suzieq.inventoryProvider.plugins.basePlugins.inventoryAsyncPlugin \
    import InventoryAsyncPlugin
from typing import Dict
import requests
import json
import string
from threading import Semaphore
from time import sleep

DEFAULT_PORTS = {"http": 80, "https": 443}
RELEVANT_FIELDS = ["primary_ip6.address", "primary_ip4.address", "site.name"]


class Netbox(InventorySource, InventoryAsyncPlugin):
    def __init__(self, input) -> None:
        self._status = "init"
        self._sem_status = Semaphore()
        super().__init__(input)

    def _load(self, netbox_config):
        if not netbox_config:
            # error
            raise ValueError("no netbox_config provided")

        use_https = netbox_config.get("use_https", False)
        if use_https:
            self._protocol = "https"
        else:
            self._protocol = "http"
        self._port = netbox_config.get(
            "port",
            DEFAULT_PORTS.get(self._protocol, None)
        )
        self._tag = netbox_config.get("tag", "null")
        self._ip_address = netbox_config.get("ip_address", None)
        self._namespace = netbox_config.get("namespace", "site.name")
        self._period = netbox_config.get("period", 3600)
        self._run_once = netbox_config.get("run_once", False)
        self._token = None
        self._password = None
        self._username = None
        credentials = netbox_config.get("credentials", None)
        if credentials:
            self._token = credentials.get("token", None)
            self._username = credentials.get("username", None)
            self._password = credentials.get("password", None)
        self._device_credentials = netbox_config.get(
            "device_credentials", None
            )
        self._session = None

    def _validate_config(self):
        errors = []
        if not self._token and (not self._username or not self._password):
            errors.append("No auth methods provided")
        if not self._ip_address:
            errors.append("No ip address provided")
        if not self._protocol:
            errors.append("Unknown protocol")
        if not self._device_credentials:
            errors.append("No device credentials provided")
        return errors

    def _init_session(self, headers):
        if not self._session:
            self._session = requests.Session()
            self._session.headers.update(headers)

    def _token_auth_header(self):
        return {"Authorization": "Token {}".format(self._token)}

    def _update_session(self, headers):
        if self._session:
            self._session.close()
            self._session = None
        self._init_session(headers)

    def retrieve_REST_data(self, url) -> Dict:
        headers = self._token_auth_header()
        if not self._session:
            self._init_session(headers)

        r = self._session.get(url, headers=headers)
        if int(r.status_code) == 200:
            res = r.json()

            data = res.get("results", [])

            if res.get("next", None):
                next_data = self.retrieve_REST_data(res["next"])
                data.extend(next_data.get("results", []))

            res["results"] = data
            res["next"] = None

            return res

        else:
            raise RuntimeError("Unable to connect to netbox:", r.json())

    def _generate_token(self) -> string:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json; indent=4",
        }
        url = "{}://{}:{}/api/users/tokens/provision/".format(
            self._protocol, self._ip_address, self._port
        )
        data = dict()
        data["username"] = self._username
        data["password"] = self._password
        data = json.dumps(data, indent=4)

        if not self._session:
            self._init_session(headers)

        r = self._session.post(url, data=data.encode("UTF-8"))
        if int(r.status_code) == 201:
            self._token = r.json().get("key", None)
            if self._token is None:
                raise RuntimeError("Unable to parse the new token")
        else:
            raise RuntimeError("Error in token generation")
        self._update_session(self._token_auth_header())

    def _parse_inventory(self, raw_inventory):
        def get_field_value(entry, fields_str):
            fields = fields_str.split(".")
            x = None
            for i, f in enumerate(fields):
                if i == 0:
                    x = entry.get(f, None)
                else:
                    x = x.get(f, None)
                if x is None:
                    return None
            return x

        inventory_list = raw_inventory.get("results", [])
        inventory = dict()

        # i can set the key as "name" rather than "id" because
        # the device name must be unique in Netbox
        for d in inventory_list:
            inventory[d["name"]] = dict()
            for ri in RELEVANT_FIELDS:
                inventory[d["name"]][ri] = get_field_value(d, ri)
            if self._namespace == "site.name"\
                    and "site.name" in RELEVANT_FIELDS:
                inventory[d["name"]]["namespace"] = inventory[d["name"]].get(
                    "site.name", ""
                )
            else:
                inventory[d["name"]]["namespace"] = self._namespace

        return inventory

    def _set_status(self, new_status):
        self._sem_status.acquire()
        self._status = new_status
        self._sem_status.release()

    def _get_status(self):
        self._sem_status.acquire()
        status = self._status
        self._sem_status.release()
        return status

    def run(self, **kwargs):
        run_once = kwargs.pop("run_once", False)

        if kwargs:
            raise ValueError("Passed unused arguments: {}".format(kwargs))

        print(threading.current_thread())
        try:
            while True:
                if self._get_status() == "stopping":
                    self._set_status("stopped")
                    break
                self._set_status("running")

                # Generate a token if not passed in the configuration file
                if self._token is None:
                    self._generate_token()

                # Retrieve data using REST
                url = "{}://{}:{}/api/dcim/devices/?tag={}".format(
                    self._protocol, self._ip_address, self._port, self._tag
                )
                raw_inventory = self.retrieve_REST_data(url)
                self._tmp_inventory = self._parse_inventory(raw_inventory)

                if not self._device_credentials.get("skip", False):
                    # Read device credentials
                    cred_load_type = self._device_credentials.get("type", None)
                    if not cred_load_type:
                        raise RuntimeError(
                            "No device credential type provided"
                        )

                    class_cred_loader = self._get_loader_class(cred_load_type)
                    if not class_cred_loader:
                        raise RuntimeError("Unknown credential loader {}"
                                           .format(cred_load_type))

                    # Instanciate and update the inventory
                    # with the device credentials
                    loader = class_cred_loader(self._device_credentials)
                    loader.load(self._tmp_inventory)

                # Write the inventory and remove the tmp one
                self.set_inventory(self._tmp_inventory)
                self._tmp_inventory.clear()

                if self._get_status() == "stopping":
                    self._set_status("stopped")
                    break
                self._set_status("sleeping")

                if self._run_once or run_once:
                    break
                print(threading.current_thread(), "starting to sleep")
                sleep(self._period)

        except Exception as e:
            raise e
        finally:
            if self._session:
                self._session.close()

    async def stop(self):
        self._set_status("stopping")
        if self._session:
            await self._session.close()
