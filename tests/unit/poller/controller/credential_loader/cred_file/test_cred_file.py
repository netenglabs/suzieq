from typing import Dict

import pytest
from suzieq.poller.controller.credential_loader.cred_file import CredFile
from tests.unit.poller.controller.utils import read_yaml_file

_DATA_PATH = [
    {
        'inventory': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/inventory/address-inventory.yaml',
        'results': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/results/address-result.yaml',
        'credential_file': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/credential_file/address-credentials.yaml'
    },
    {
        'inventory': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/inventory/hostname-inventory.yaml',
        'results': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/results/hostname-result.yaml',
        'credential_file': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/credential_file/hostname-credentials.yaml'
    }
]


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.credential_loader
@pytest.mark.credential_file
@pytest.mark.parametrize('data_path', _DATA_PATH)
def test_credential_load(data_path: Dict):
    """Test if the credentials are loaded correctly

    Args:
        data_path (Dict): data to read
    """
    init_data = {
        'name': 'cred0',
        'type': 'cred-file',
        'path': data_path['credential_file']
    }

    cf = CredFile(init_data)
    inv = read_yaml_file(data_path['inventory'])
    cf.load(inv)

    assert inv == read_yaml_file(data_path['results'])
