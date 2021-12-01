"""Netbox module

This module contains the methods to connect with a Netbox REST server
and retrieve the devices inventory

Classes:
    Netbox: this class dinamically retrieve the inventory from Netbox
"""
import threading
from typing import Dict
import json
from threading import Semaphore
from time import sleep
import requests
from suzieq.inventory_provider.plugins.base_plugins.inventory_source \
    import InventorySource
from suzieq.inventory_provider.plugins.base_plugins.inventory_async_plugin \
    import InventoryAsyncPlugin

_DEFAULT_PORTS = {"http": 80, "https": 443}
_RELEVANT_FIELDS = [
    "name",
    "primary_ip6.address",
    "primary_ip4.address",
    "site.name"
]


class Netbox(InventorySource, InventoryAsyncPlugin):
    """This class is used to dinamically retrieve the inventory from Netbox
       and also retrieve for each device in the inventory its credentials

    """

    def __init__(self, config_data: dict) -> None:
        self._status = "init"
        self._sem_status = Semaphore()
        self._session: requests.Session = None
        self._tag = ""
        self._ip_address = ""
        self._namespace = ""
        self._period = 3600
        self._run_once = ""
        self._token = ""
        self._password = ""
        self._username = ""

        super().__init__(config_data)

    def _load(self, input_data: dict):
        """Load the configuration data in the object

        Args:
            input_data ([dict]): Input configuration data

        Raises:
            ValueError: This exception is called if the netbox configuration
                        is empty
        """

        if not input_data:
            # error
            raise ValueError("no netbox_config provided")

        use_https = input_data.get("use_https", False)
        if use_https:
            self._protocol = "https"
        else:
            self._protocol = "http"
        self._port = input_data.get(
            "port",
            _DEFAULT_PORTS.get(self._protocol, None)
        )
        self._tag = input_data.get("tag", "null")
        self._ip_address = input_data.get("ip_address", None)
        self._namespace = input_data.get("namespace", "site.name")
        self._period = input_data.get("period", 3600)
        self._run_once = input_data.get("run_once", False)
        self._token = None
        self._password = None
        self._username = None
        credentials = input_data.get("credentials", None)
        if credentials:
            self._token = credentials.get("token", None)
            self._username = credentials.get("username", None)
            self._password = credentials.get("password", None)
        self._device_credentials = input_data.get(
            "device_credentials", None
        )

    def _validate_config(self) -> list:
        """Validates the loaded configuration

        Returns:
            list: the list of errors
        """
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

    def _update_inventory_format(self, input_inv_format: dict = None):
        netbox_inv_format = {
            "hostname": "name",
            "namespace": "namespace",
            "ipv4": "primary_ip4.address",
            "ipv6": "primary_ip6.address",
            "credentials": "credentials"
        }
        super()._update_inventory_format(
            input_inv_format=netbox_inv_format
        )

    def _init_session(self, headers: dict):
        """Initialize the session property

        Args:
            headers ([dict]): headers to initialize the session
        """
        if not self._session:
            self._session = requests.Session()
            self._session.headers.update(headers)

    def _token_auth_header(self) -> dict:
        """Generate the token authorization header

        Returns:
            dict: token authorization header
        """
        return {"Authorization": f"Token {self._token}"}

    def _update_session(self, headers: dict):
        """Update the session. If the session was already set up, this function
           will close it and initialize it again

        Args:
            headers ([dict]): session headers
        """
        if self._session:
            self._session.close()
            self._session = None
        self._init_session(headers)

    def retrieve_rest_data(self, url: str) -> Dict:
        """Perform an HTTP GET to the <url> parameter.

        Args:
            url (str): HTTP GET target

        Raises:
            RuntimeError: Unable to connect to the REST server

        Returns:
            Dict: content of the HTTP GET
        """
        headers = self._token_auth_header()
        if not self._session:
            self._init_session(headers)

        response = self._session.get(url, headers=headers)
        if int(response.status_code) == 200:
            res = response.json()

            data = res.get("results", [])

            if res.get("next", None):
                next_data = self.retrieve_rest_data(res["next"])
                data.extend(next_data.get("results", []))

            res["results"] = data
            res["next"] = None

            return res

        else:
            raise RuntimeError("Unable to connect to netbox:", response.json())

    def _generate_token(self) -> str:
        """Contact Netobox and ask to generate a token if only username and
           password were provided in the configuration.

        Raises:
            RuntimeError: Unable to parse the token
            RuntimeError: The server response has an invalid status code

        Returns:
            str: a string containing the generated token
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json; indent=4",
        }
        url = f"{self._protocol}://{self._ip_address}:{self._port}"\
            "/api/users/tokens/provision/"
        data = dict()
        data["username"] = self._username
        data["password"] = self._password
        data = json.dumps(data, indent=4)

        if not self._session:
            self._init_session(headers)

        response = self._session.post(url, data=data.encode("UTF-8"))
        if int(response.status_code) == 201:
            self._token = response.json().get("key", None)
            if self._token is None:
                raise RuntimeError("Unable to parse the new token")
        else:
            raise RuntimeError("Error in token generation")
        self._update_session(self._token_auth_header())

    def _parse_inventory(self, raw_inventory: dict) -> Dict:
        """parse the raw inventory collected from the server and generates
           a new inventory with only the required informations

        Args:
            raw_inventory (dict): raw inventory received from the server

        Returns:
            Dict: a dictionary containing the inventory
        """
        def get_field_value(entry, fields_str):
            fields = fields_str.split(".")
            cur_field = None
            for i, field in enumerate(fields):
                if i == 0:
                    cur_field = entry.get(field, None)
                else:
                    cur_field = cur_field.get(field, None)
                if cur_field is None:
                    return None
            return cur_field

        inventory_list = raw_inventory.get("results", [])
        inventory = dict()

        # i can set the key as "name" rather than "id" because
        # the device name must be unique in Netbox
        for device in inventory_list:
            inventory[device["name"]] = dict()
            for rel_field in _RELEVANT_FIELDS:
                inventory[device["name"]][rel_field] = \
                    get_field_value(device, rel_field)
            if self._namespace == "site.name"\
                    and "site.name" in _RELEVANT_FIELDS:
                inventory[device["name"]]["namespace"] = \
                    inventory[device["name"]].get("site.name", "")
            else:
                inventory[device["name"]]["namespace"] = self._namespace

        return inventory

    def _set_status(self, new_status: str):
        self._sem_status.acquire()
        self._status = new_status
        self._sem_status.release()

    def _get_status(self) -> str:
        self._sem_status.acquire()
        status = self._status
        self._sem_status.release()
        return status

    def _set_session(self, session: requests.Session):
        self._session = session

    def run(self, **kwargs):
        run_once = kwargs.pop("run_once", False)

        if kwargs:
            raise ValueError(f"Passed unused arguments: {kwargs}")

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
                url = f"{self._protocol}://{self._ip_address}:{self._port}"\
                    f"/api/dcim/devices/?tag={self._tag}"
                raw_inventory = self.retrieve_rest_data(url)
                tmp_inventory = self._parse_inventory(raw_inventory)

                if not self._device_credentials.get("skip", False):
                    # Read device credentials
                    cred_load_type = self._device_credentials.get("type", None)
                    if not cred_load_type:
                        raise RuntimeError(
                            "No device credential type provided"
                        )

                    class_cred_loader = self._get_loader_class(cred_load_type)
                    if not class_cred_loader:
                        raise RuntimeError(f"Unknown credential loader \
                        {cred_load_type}")

                    # Instanciate and update the inventory
                    # with the device credentials
                    loader = class_cred_loader(self._device_credentials)
                    loader.load(tmp_inventory)

                # Write the inventory and remove the tmp one
                self.set_inventory(tmp_inventory)
                tmp_inventory.clear()

                if self._get_status() == "stopping":
                    self._set_status("stopped")
                    break
                self._set_status("sleeping")

                if self._run_once or run_once:
                    break
                print(threading.current_thread(), "starting to sleep")
                sleep(self._period)

        except Exception as exc:
            raise exc
        finally:
            if self._session:
                self._session.close()

    def stop(self):
        self._set_status("stopping")
        if self._session:
            self._session.close()
