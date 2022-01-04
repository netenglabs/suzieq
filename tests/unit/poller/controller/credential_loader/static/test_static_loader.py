from typing import Dict
import pytest
from suzieq.poller.controller.credential_loader.static import StaticLoader
from tests.unit.poller.controller.utils import read_yaml_file

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
@pytest.mark.credential_loader
@pytest.mark.static_credential_loader
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
        'password': 'plain:password'
    }

    sl = StaticLoader(init_data)

    assert sl._username == init_data['username']
    assert sl._passphrase == init_data['ssh-passphrase'].split(':')[1]
    assert sl._password == init_data['password'].split(':')[1]

    inv = read_yaml_file(data_path['inventory'])
    sl.load(inv)

    assert inv == read_yaml_file(data_path['results'])
