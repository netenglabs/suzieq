import asyncio
from typing import Dict
from pydantic import ValidationError

import pytest
from suzieq.poller.controller.source.native import SqNativeFile
from tests.unit.poller.shared.utils import (get_src_sample_config,
                                            read_yaml_file)

# pylint: disable=redefined-outer-name

_DATA_PATH = [
    {
        'hosts': 'tests/unit/poller/controller/sources/native/data/inventory/'
        'valid_hosts.yaml',

        'results': 'tests/unit/poller/controller/sources/native/data/results/'
        'results.yaml'}
]


@pytest.fixture
def default_config() -> Dict:
    """return a default native configuration

    Yields:
        Dict: native config
    """
    yield get_src_sample_config('native')


@pytest.mark.controller_source_native
@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.parametrize('data_path', _DATA_PATH)
@pytest.mark.asyncio
async def test_valid_config(data_path: str, default_config):
    """Test if the inventory is loaded correctly

    Args:
        data_path (str): file containing result and hosts
    """
    config = default_config
    config['hosts'] = read_yaml_file(data_path['hosts'])

    src = SqNativeFile(config.copy(), validate=True)

    assert src.name == config['name']
    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert cur_inv == read_yaml_file(data_path['results'])


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_native
@pytest.mark.asyncio
async def test_invalid_hosts(default_config):
    """Test invalid hosts param
    """

    config = default_config.copy()

    # empty hosts
    config['hosts'] = []

    with pytest.raises(ValidationError):
        SqNativeFile(config, validate=True)

    # 'hosts' not a list
    config = default_config.copy()
    config['hosts'] = {'not': 'valid'}
    with pytest.raises(ValidationError):
        SqNativeFile(config, validate=True)

    # hosts field not set
    config = default_config.copy()
    config.pop('hosts')
    with pytest.raises(ValidationError):
        SqNativeFile(config, validate=True)

    # invalid hosts
    config = default_config.copy()
    config['hosts'] = [
        # no 'url' key
        {'not-url': 'ssh://vagrant@192.168.0.1 password=my-password'},
        # 'password:' instead of 'password='
        {'url': 'ssh://vagrant@192.168.0.1 password:my-password'},
        # not a dictionary
        "url= ssh://vagrant@192.168.0.1 password=my-password",
        # key doesn't exists
        {'url': 'ssh://vagrant@192.168.0.1 keyfile=wrong/key/path'},
    ]
    try:
        SqNativeFile(config, validate=True)
    except ValidationError as e:
        # each invalid host will raise an exception
        assert len(e.errors()) == len(config['hosts'])


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_native
@pytest.mark.asyncio
def test_validate_inventory(default_config):
    """Check that validate_inventory raise correctly
    """
    config = default_config

    # wrong transport
    config['hosts'] = [
        {'url': 'wrong://vagrant@192.168.0.1 password=my-password'}
    ]
    with pytest.raises(ValidationError, match=r".*'wrong' not supported.*"):
        SqNativeFile(config.copy(), validate=True)


@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_native
@pytest.mark.asyncio
@pytest.mark.parametrize('address', [
    '192.168.0',
    '192.168.00.1',
    '10.0.1.9000',
    'not_a_domain.com'
])
def test_wrong_addresses(address: str, default_config):
    """Validate wrong addresses formats

    Args:
        address (str): wrong address to validate
    """
    config = default_config
    config['hosts'] = [
        {'url': f'ssh://vagrant@{address} password=my-password'}
    ]
    with pytest.raises(ValidationError,
                       match=r'.*Invalid hostname or address.*'):
        SqNativeFile(config.copy(), validate=True)
