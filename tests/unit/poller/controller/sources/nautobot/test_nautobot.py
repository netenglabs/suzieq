"""Tests using Nautobot as a SuzieQ inventory source."""

import asyncio
import urllib.parse
import json
from typing import Dict, Any
import pytest
import requests_mock

from suzieq.poller.controller.source.nautobot import Nautobot

from tests.unit.poller.shared.utils import get_src_sample_config


def get_json(filename: str) -> Dict[str, Any]:
    """Read JSON file"""
    with open(filename, encoding="utf-8") as f:
        response_json = json.load(f)
    return response_json


@pytest.fixture
def default_config() -> Dict:
    """Generate a default Nautobot config

    Returns:
        Dict: Nautobot config

    Yields:
        Iterator[Dict]: [description]
    """
    yield get_src_sample_config("nautobot")


_RESPONSE_DATA_DIR = "tests/unit/poller/controller/sources/nautobot/responses/"

_TEST_CONFIGS = [
    {
        "server_config": {
            "namespace": "nautobot-ns",
            "use_ssl": True,
            "port": 8080,
        },
        "test_params": {
            "test_urls": {
                "https://127.0.0.1:8080/api/": get_json(
                    _RESPONSE_DATA_DIR + "base_response.json"
                ),
                "https://127.0.0.1:8080/api/dcim/devices/": get_json(
                    _RESPONSE_DATA_DIR + "all-devices.json"
                ),
                # ang01-edge-01
                "https://127.0.0.1:8080/api/ipam/ip-addresses/fe06d6c1-b233-4499-b5e9-f36af5a72dc3/": get_json(
                    _RESPONSE_DATA_DIR + "ang01-edge-01_ip.json"
                ),
                "https://127.0.0.1:8080/api/dcim/locations/279b30b2-7aee-45be-8086-9d151ce22799/": get_json(
                    _RESPONSE_DATA_DIR + "ang01-edge-01_location.json"
                ),
                # azd01-leaf-07
                "https://127.0.0.1:8080/api/ipam/ip-addresses/94f6cbb7-2897-4b9e-91ef-573f9c0b44d8/": get_json(
                    _RESPONSE_DATA_DIR + "azd01-leaf-07_ip.json"
                ),
                "https://127.0.0.1:8080/api/dcim/locations/f6aa82a1-c61a-4b3e-8f4d-03e09e32feb6/": get_json(
                    _RESPONSE_DATA_DIR + "azd01-leaf-07_location.json"
                ),
            },
            "expected_result": get_json(
                _RESPONSE_DATA_DIR + "all-devices_expected.json"
            ),
        },
    },
    {
        "server_config": {
            "namespace": "group-by-location",
            "use_ssl": True,
            "port": 8080,
        },
        "test_params": {
            "test_urls": {
                "https://127.0.0.1:8080/api/": get_json(
                    _RESPONSE_DATA_DIR + "base_response.json"
                ),
                "https://127.0.0.1:8080/api/dcim/devices/": get_json(
                    _RESPONSE_DATA_DIR + "all-devices.json"
                ),
                # ang01-edge-01
                "https://127.0.0.1:8080/api/ipam/ip-addresses/fe06d6c1-b233-4499-b5e9-f36af5a72dc3/": get_json(
                    _RESPONSE_DATA_DIR + "ang01-edge-01_ip.json"
                ),
                "https://127.0.0.1:8080/api/dcim/locations/279b30b2-7aee-45be-8086-9d151ce22799/": get_json(
                    _RESPONSE_DATA_DIR + "ang01-edge-01_location.json"
                ),
                # azd01-leaf-07
                "https://127.0.0.1:8080/api/ipam/ip-addresses/94f6cbb7-2897-4b9e-91ef-573f9c0b44d8/": get_json(
                    _RESPONSE_DATA_DIR + "azd01-leaf-07_ip.json"
                ),
                "https://127.0.0.1:8080/api/dcim/locations/f6aa82a1-c61a-4b3e-8f4d-03e09e32feb6/": get_json(
                    _RESPONSE_DATA_DIR + "azd01-leaf-07_location.json"
                ),
            },
            "expected_result": get_json(
                _RESPONSE_DATA_DIR + "all-devices_by_location_expected.json"
            ),
        },
    },
    {
        "server_config": {
            "namespace": "nautobot-ns",
            "use_ssl": True,
            "port": 8080,
            "device_filters": {"name": "ang01-edge-01"},
        },
        "test_params": {
            "test_urls": {
                "https://127.0.0.1:8080/api/": get_json(
                    _RESPONSE_DATA_DIR + "base_response.json"
                ),
                "https://127.0.0.1:8080/api/dcim/devices/?"
                + urllib.parse.urlencode({"name": "ang01-edge-01"}): get_json(
                    _RESPONSE_DATA_DIR + "ang01-edge-01_device.json"
                ),
                "https://127.0.0.1:8080/api/ipam/ip-addresses/fe06d6c1-b233-4499-b5e9-f36af5a72dc3/": get_json(
                    _RESPONSE_DATA_DIR + "ang01-edge-01_ip.json"
                ),
                "https://127.0.0.1:8080/api/dcim/locations/279b30b2-7aee-45be-8086-9d151ce22799/": get_json(
                    _RESPONSE_DATA_DIR + "ang01-edge-01_location.json"
                ),
            },
            "expected_result": get_json(
                _RESPONSE_DATA_DIR + "ang01-edge-01_expected.json"
            ),
        },
    },
    {
        "server_config": {
            "namespace": "nautobot-ns",
            "use_ssl": True,
            "port": 8080,
            "device_filters": {"location": "AZD01"},
        },
        "test_params": {
            "test_urls": {
                "https://127.0.0.1:8080/api/": get_json(
                    _RESPONSE_DATA_DIR + "base_response.json"
                ),
                "https://127.0.0.1:8080/api/dcim/devices/?"
                + urllib.parse.urlencode({"location": "AZD01"}): get_json(
                    _RESPONSE_DATA_DIR + "azd01-leaf-07_device.json"
                ),
                "https://127.0.0.1:8080/api/ipam/ip-addresses/94f6cbb7-2897-4b9e-91ef-573f9c0b44d8/": get_json(
                    _RESPONSE_DATA_DIR + "azd01-leaf-07_ip.json"
                ),
                "https://127.0.0.1:8080/api/dcim/locations/f6aa82a1-c61a-4b3e-8f4d-03e09e32feb6/": get_json(
                    _RESPONSE_DATA_DIR + "azd01-leaf-07_location.json"
                ),
            },
            "expected_result": get_json(
                _RESPONSE_DATA_DIR + "azd01-leaf-07_expected.json"
            ),
        },
    },
]


def update_config(server_conf: Dict, config: Dict) -> Dict:
    """Set the Nautobot configuration correctly to connect to the
    server

    Args:
        server_conf (Dict): server configuration
        config (Dict): Nautobot configuration

    Returns:
        Dict: updated Nautobot configuration
    """
    config["namespace"] = server_conf["namespace"]
    config["url"] = "http"
    if server_conf["use_ssl"]:
        config["url"] = "https"
        if server_conf["use_ssl"] == "self-signed":
            config["ssl-verify"] = False
    config["url"] += f'://127.0.0.1:{server_conf["port"]}'
    config["device_filters"] = server_conf.get("device_filters", None)
    return config


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_nautobot
@pytest.mark.asyncio
@pytest.mark.parametrize("test_conf", _TEST_CONFIGS)
async def test_valid_config(test_conf, default_config):
    """Tests if the pulled inventory is valid

    Args:
        test_conf(Dict): test configuration
    """
    config = update_config(test_conf["server_config"], default_config)

    src = Nautobot(config.copy())

    with requests_mock.Mocker() as m:
        for endpoint, resp in test_conf["test_params"]["test_urls"].items():
            m.get(endpoint, json=resp)
        await asyncio.wait_for(src.run(), 10)
        cur_inv = await asyncio.wait_for(src.get_inventory(), 5)

    assert cur_inv == test_conf["test_params"]["expected_result"], cur_inv
