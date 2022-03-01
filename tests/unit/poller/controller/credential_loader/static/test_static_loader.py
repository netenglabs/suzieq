from typing import Dict
from pydantic import ValidationError

import pytest
from suzieq.poller.controller.credential_loader.static import (StaticLoader,
                                                               StaticModel)
from tests.unit.poller.shared.utils import read_yaml_file

_DATA_PATH = [
    {
        'inventory': 'tests/unit/poller/controller/credential_loader/static'
        '/data/inventory.yaml',
        'results': 'tests/unit/poller/controller/credential_loader/static'
        '/data/results.yaml'
    }
]


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_credential_loader
@pytest.mark.controller_credential_loader_static
@pytest.mark.parametrize('data_path', _DATA_PATH)
def test_load(data_path: Dict):
    """Test if the credentials are loaded correctly

    The info loaded from the configuration must be override
    the one inside a node only if it was not specified

    Args:
        data_path (Dict): input dictionary containing the inventory
        and the results
    """
    # the username will be overrided by the content of the inventory
    init_data = {
        'name': 'n',
        'username': 'user-to-override',
        'ssh-passphrase': 'plain:my-pass',
        'password': 'plain:password',
        'keyfile': 'my/keyfile'
    }

    valid_data = StaticModel(**init_data).dict(by_alias=True)

    sl = StaticLoader(valid_data)

    # pylint: disable=protected-access
    assert sl._data.username == init_data['username']
    assert sl._data.ssh_passphrase == init_data['ssh-passphrase'].split(':')[1]
    assert sl._data.password == init_data['password'].split(':')[1]
    assert sl._data.keyfile == init_data['keyfile']

    inv = read_yaml_file(data_path['inventory'])
    sl.load(inv)

    assert inv == read_yaml_file(data_path['results'])


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_credential_loader
@pytest.mark.controller_credential_loader_static
def test_no_env_var():
    """Testing a password retrieved from an unexisting env var
    """

    with pytest.raises(ValidationError):
        StaticModel(**{'name': 'n', 'password': 'env:WRONG_ENV'})


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_credential_loader
@pytest.mark.controller_credential_loader_static
def test_variables_init(monkeypatch):
    """Test parameters are correctly set up
    """
    # pylint: disable=protected-access
    ask_password = 'ask_password'
    env_password = 'env_password'
    plain_passphrase = 'my-pass'

    # 'env' and 'plain' values
    init_data = {
        'name': 'n',
        'ssh-passphrase': f'plain:{plain_passphrase}',
        'password': 'env:SUZIEQ_ENV_PASSWORD'
    }
    monkeypatch.setenv('SUZIEQ_ENV_PASSWORD', env_password)
    sl = StaticModel(**init_data)

    assert sl.ssh_passphrase == plain_passphrase
    assert sl.password == env_password

    # 'ask' values
    init_data = {
        'name': 'n',
        'password': 'ask'
    }
    valid_data = StaticModel(**init_data).dict(by_alias=True)
    monkeypatch.setattr('getpass.getpass', lambda x: ask_password)
    sl = StaticLoader(valid_data)

    assert sl._data.password == ask_password

    # unknown parameter
    init_data = {
        'name': 'n',
        'username': 'user',
        'unknown': 'parameter'
    }
    with pytest.raises(ValidationError):
        StaticModel(**init_data)
