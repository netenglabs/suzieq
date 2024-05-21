from typing import Dict

import pytest
from pydantic import ValidationError

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
        'key-passphrase': 'plain:my-pass',
        'password': 'plain:password',
        'keyfile': 'my/keyfile',
        'enable-password': 'my-password'
    }

    valid_data = StaticModel(**init_data).dict(by_alias=True)

    sl = StaticLoader(valid_data)

    assert sl._data.username == init_data['username']
    assert sl._data.key_passphrase == init_data['key-passphrase'].split(':')[1]
    assert sl._data.password == init_data['password'].split(':')[1]
    assert sl._data.keyfile == init_data['keyfile']
    assert sl._data.enable_password == init_data['enable-password']

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
    ask_password = 'ask_password'
    env_password = 'env_password'
    ask_username = 'ask_username'
    env_username = 'env_username'
    plain_passphrase = 'my-pass'

    # 'env' and 'plain' values
    init_data = {
        'name': 'n',
        'username': 'env:SUZIEQ_ENV_USERNAME',
        'key-passphrase': f'plain:{plain_passphrase}',
        'password': 'env:SUZIEQ_ENV_PASSWORD'
    }
    monkeypatch.setenv('SUZIEQ_ENV_PASSWORD', env_password)
    monkeypatch.setenv('SUZIEQ_ENV_USERNAME', env_username)
    sl = StaticModel(**init_data)

    assert sl.key_passphrase == plain_passphrase
    assert sl.password == env_password
    assert sl.username == env_username

    # 'ask' values
    init_data = {
        'name': 'n',
        'username': 'ask',
        'password': 'ask'
    }
    valid_data = StaticModel(**init_data).dict(by_alias=True)
    mock_get_pass = MockGetPass([ask_username, ask_password])
    monkeypatch.setattr('getpass.getpass', mock_get_pass)
    sl = StaticLoader(valid_data)

    assert sl._data.password == ask_password
    assert sl._data.username == ask_username

    # unknown parameter
    init_data = {
        'name': 'n',
        'username': 'user',
        'unknown': 'parameter'
    }
    with pytest.raises(ValidationError):
        StaticModel(**init_data)


class MockGetPass:
    """
   Mocks `getpass.getpass` for testing, cycling through a list of predefined
   responses.

   Attributes:
       responses (list): A list of responses to simulate sequential user inputs.
       call_count (int): Tracks calls to provide the next response in the list.
   """

    def __init__(self, responses: list):
        """
        Initializes the mock with responses and resets call count.

        Args:
            responses: Simulated user inputs.
        """
        self.responses = responses
        self.call_count = 0

    def __call__(self, prompt=''):
        """
        Returns the next response from the list, mimicking user input.

        Args:
            prompt: Unused, present for compatibility.

        Returns:
            The next simulated user input.
        """
        response = self.responses[self.call_count]
        self.call_count += 1
        if self.call_count >= len(self.responses):
            self.call_count = 0
        return response
