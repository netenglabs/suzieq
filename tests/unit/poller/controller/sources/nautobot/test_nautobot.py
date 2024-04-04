import asyncio
import pytest
import requests_mock

from suzieq.poller.controller.source.nautobot import Nautobot

from tests.unit.poller.controller.sources.nautobot.fixtures import (
    TEST_URLS,
    EXPECTED_RESULT,
)

from typing import Dict

from tests.unit.poller.shared.utils import get_src_sample_config


@pytest.fixture
def default_config() -> Dict:
    """Generate a default netbox config

    Returns:
        Dict: netbox config

    Yields:
        Iterator[Dict]: [description]
    """
    yield get_src_sample_config("nautobot")


# _SERVER_CONFIGS = [
#     {
#         "namespace": "nautobot-ns",
#         "use_ssl": "",
#         # 'tag': ['suzieq'],
#         # "count": 20,
#         "port": 8080,
#     },
#     {
#         "namespace": "nautobot-location-name",
#         "use_ssl": "self-signed",
#         # 'tag': ['suzieq', 'suzieq-2'],
#         "count": 90,
#         "port": 8080,
#     },
# ]
# Re-organizing tests
_TEST_CONFIGS = [
    {
        "server_config": {
            "namespace": "nautobot-ns",
            "use_ssl": "",
            "port": 8080,
        },
        "test_urls": TEST_URLS,
        "expected_result": EXPECTED_RESULT
    },
    {
        "server_config": {
            "namespace": "netbox-ns",
            "use_ssl": "",
            "port": 8080,
        },
        "test_urls": TEST_URLS,
        "expected_result": EXPECTED_RESULT
    }
]


def update_config(server_conf: Dict, config: Dict) -> Dict:
    """Set the netbox configuration correctly to connect to the
    server

    Args:
        server_conf (Dict): server configuration
        config (Dict): netbox configuration

    Returns:
        Dict: updated netbox configuration
    """
    # config['tag'] = server_conf['tag']
    config["namespace"] = server_conf["namespace"]
    config["url"] = "http"
    if server_conf["use_ssl"]:
        config["url"] = "https"
        if server_conf["use_ssl"] == "self-signed":
            config["ssl-verify"] = False
    config["url"] += f'://127.0.0.1:{server_conf["port"]}'
    return config


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_nautobot
@pytest.mark.asyncio
# @pytest.mark.parametrize("server_conf", _SERVER_CONFIGS)
@pytest.mark.parametrize("test_conf", _TEST_CONFIGS)
# async def test_valid_config(server_conf: Dict, default_config):
async def test_valid_config(test_conf, default_config):
    """Tests if the pulled inventory is valid

    Args:
        server_conf(Dict): server configuration
    """
    config = default_config
    config = update_config(test_conf["server_config"], config)

    src = Nautobot(config.copy())

    with requests_mock.Mocker() as m:
        for endpoint, resp in test_conf["test_urls"].items():
            m.get(endpoint, json=resp)
        await asyncio.wait_for(src.run(), 10)
        cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == test_conf["expected_result"], (cur_inv, test_conf["expected_result"])
