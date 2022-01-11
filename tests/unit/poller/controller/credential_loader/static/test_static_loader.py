from typing import Dict

import pytest
from suzieq.poller.controller.credential_loader.static import StaticLoader
from suzieq.shared.exceptions import InventorySourceError
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
        'username': 'user-to-override',
        'ssh-passphrase': 'plain:my-pass',
        'password': 'plain:password',
        'keyfile': 'my/keyfile'
    }

    sl = StaticLoader(init_data)

    # pylint: disable=protected-access
    assert sl._username == init_data['username']
    assert sl._passphrase == init_data['ssh-passphrase'].split(':')[1]
    assert sl._password == init_data['password'].split(':')[1]
    assert sl._keyfile == init_data['keyfile']

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
    init_data = {
        'password': 'env:WRONG_ENV',
    }

    with pytest.raises(InventorySourceError):
        StaticLoader(init_data)


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
        'ssh-passphrase': f'plain:{plain_passphrase}',
        'password': 'env:SUZIEQ_ENV_PASSWORD'
    }
    monkeypatch.setenv('SUZIEQ_ENV_PASSWORD', env_password)
    sl = StaticLoader(init_data)

    assert sl._passphrase == plain_passphrase
    assert sl._password == env_password

    # 'ask' values
    init_data = {
        'password': 'ask'
    }
    monkeypatch.setattr('getpass.getpass', lambda x: ask_password)
    sl = StaticLoader(init_data)

    assert sl._password == ask_password

    # unsupported method
    init_data = {
        'password': 'uns-method'
    }
    with pytest.raises(InventorySourceError):
        StaticLoader(init_data)

    # unknown parameter
    init_data = {
        'username': 'user',
        'unknown': 'parameter'
    }
    with pytest.raises(InventorySourceError):
        StaticLoader(init_data)
