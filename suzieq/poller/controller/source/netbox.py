"""Netbox module

This module contains the methods to connect with a Netbox REST server
and retrieve the devices inventory

Classes:
    Netbox: this class dinamically retrieve the inventory from Netbox
"""
from typing import Dict, List
from urllib.parse import urlparse
from threading import Semaphore
import requests
from suzieq.poller.controller.source.base_source \
    import Source
from suzieq.poller.controller.inventory_async_plugin \
    import InventoryAsyncPlugin
from suzieq.shared.exceptions import InventorySourceError

_DEFAULT_PORTS = {"http": 80, "https": 443}
_RELEVANT_FIELDS = [
    "name",
    "primary_ip6.address",
    "primary_ip4.address",
    "site.name"
]


class Netbox(Source, InventoryAsyncPlugin):
    """This class is used to dinamically retrieve the inventory from Netbox
       and also retrieve for each device in the inventory its credentials

    """

    def __init__(self, config_data: dict) -> None:
        self._status = "init"
        self._sem_status = Semaphore()
        self._session: requests.Session = None
        self._tag = ""
        self._host = ""
        self._namespace = ""
        self._period = 3600
        self._run_once = ""
        self._token = ""
        # Contains CredentialLoader object with device credentials
        self._auth = None
        # Contains a dictionary with devices specifications
        self._device = None

        self._sleep_sem = Semaphore()
        # pylint: disable=consider-using-with
        self._sleep_sem.acquire()

        super().__init__(config_data)

    def _load(self, input_data: dict):
        """Load the configuration data in the object

        Args:
            input_data ([dict]): Input configuration data

        Raises:
            ValueError: netbox url is empty
            ValueError: netbox configuration
                        is empty
        """

        if not input_data:
            # error
            raise ValueError("no netbox_config provided")

        url = input_data.get("url", "")
        if not url:
            raise ValueError("netbox url not provided")

        url_data = urlparse(url)
        self._protocol = url_data.scheme or "http"
        self._port = url_data.port or _DEFAULT_PORTS.get(self._protocol, None)
        self._host = url_data.hostname

        if not self._protocol or not self._port or not self._host:
            raise InventorySourceError("netbox: invalid url provided")

        self._tag = input_data.get("tag", "null")
        self._namespace = input_data.get("namespace", "site.name")
        self._period = input_data.get("period", 3600)
        self._run_once = input_data.get("run_once", False)
        self._token = input_data.get("token", None)
        self._auth = input_data.get("auth", None)
        self._device = input_data.get("device", None)

    def _validate_config(self, input_data) -> list:
        """Validates the loaded configuration

        Returns:
            list: the list of errors
        """
        errors = []
        if not input_data.get("token"):
            errors.append("No netbox token provided")
        if not input_data.get("url"):
            errors.append("No netbox url provided")
        if not input_data.get("auth"):
            errors.append("No device auth provided")
        return errors

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

    def _parse_inventory(self, raw_inventory: dict) -> List[Dict]:
        """parse the raw inventory collected from the server and generates
           a new inventory with only the required informations

        Args:
            raw_inventory (dict): raw inventory received from the server

        Returns:
            List[Dict]: a list containing the inventory
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
        inventory = {}

        # i can set the key as "name" rather than "id" because
        # the device name must be unique in Netbox
        for device in inventory_list:
            inventory[device["name"]] = {}
            for rel_field in _RELEVANT_FIELDS:
                if rel_field == "name":
                    inventory[device["name"]]["id"] = \
                        get_field_value(device, rel_field)
                elif rel_field == "primary_ip6.address":
                    inventory[device["name"]]["ipv6"] = \
                        get_field_value(device, rel_field)
                elif rel_field == "primary_ip4.address":
                    inventory[device["name"]]["ipv4"] = \
                        get_field_value(device, rel_field)

            if inventory[device["name"]]["ipv4"]:
                inventory[device["name"]
                          ]["address"] = inventory[device["name"]]["ipv4"]
            elif inventory[device["name"]]["ipv6"]:
                inventory[device["name"]
                          ]["address"] = inventory[device["name"]]["ipv6"]

            inventory[device["name"]]["devtype"] = self._device.get("devtype")

            # only ssh supported for now
            inventory[device["name"]]["transport"] = self._device.get(
                "transport") or "ssh"
            inventory[device["name"]]["port"] = 22

            if self._namespace == "site.name"\
                    and "site.name" in _RELEVANT_FIELDS:
                inventory[device["name"]]["namespace"] = \
                    inventory[device["name"]].get("site.name", "")
            else:
                inventory[device["name"]]["namespace"] = self._namespace

        return list(inventory.values())

    def _set_status(self, new_status: str):
        with self._sem_status:
            self._status = new_status

    def _get_status(self) -> str:
        with self._sem_status:
            status = self._status
        return status

    def _set_session(self, session: requests.Session):
        self._session = session

    def run(self, **kwargs):
        run_once = kwargs.pop("run_once", False)

        if kwargs:
            raise ValueError(f"Passed unused arguments: {kwargs}")

        try:
            while True:
                if self._get_status() == "stop":
                    break
                self._set_status("running")

                # Retrieve data using REST
                url = f"{self._protocol}://{self._host}:{self._port}"\
                    f"/api/dcim/devices/?tag={self._tag}"
                raw_inventory = self.retrieve_rest_data(url)
                tmp_inventory = self._parse_inventory(raw_inventory)
                # load credentials into the inventory
                self._auth.load(tmp_inventory)

                # Write the inventory and remove the tmp one

                self.set_inventory(tmp_inventory)
                tmp_inventory.clear()

                if self._get_status() == "stop":
                    break

                if self._run_once or run_once:
                    break

                # pylint: disable=consider-using-with
                self._sleep_sem.acquire(timeout=self._period)

        except Exception as exc:
            raise exc
        finally:
            if self._session:
                self._session.close()

    def stop(self):
        self._set_status("stop")
        if self._session:
            self._session.close()
        self._sleep_sem.release()
