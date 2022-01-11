from typing import Dict
from unittest.mock import patch

import pytest
from suzieq.poller.controller.credential_loader.cred_file import CredFile
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.shared.utils import read_yaml_file

_DATA_PATH = [
    {
        'inventory': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/inventory/address-inventory.yaml',
        'results': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/results/address-result.yaml',
        'credentials': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/credential_file/address-credentials.yaml'
    },
    {
        'inventory': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/inventory/hostname-inventory.yaml',
        'results': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/results/hostname-result.yaml',
        'credentials': 'tests/unit/poller/controller/credential_loader/'
        'cred_file/data/credential_file/hostname-credentials.yaml'
    }
]

_WRONG_CRED_FILE = ['tests/unit/poller/controller/credential_loader/'
                    'cred_file/data/wrong_files/empty.yaml',
                    'tests/unit/poller/controller/credential_loader/cred_file/'
                    'data/wrong_files/not_a_list.yaml',
                    'tests/unit/poller/controller/credential_loader/cred_file/'
                    'data/wrong_files/not_a_yaml_file.yaml']


def init_mock(self, data: Dict):
    """CredFile.init mock function

    This function load the content of data['path'] into the CredFile
    object.
    The original version of the init function expect to read the
    credentials from a path.
    This mock function loads the data directly into object


    The credentials are passed into 'path' because otherwise I need to
    update also the plugin validation. If for example I used the 'cred'
    key, the plugin will raise an exception because it doesn't recognize
    the 'cred' field

    Args:
        data (Dict): dictionary with credentials under 'path' key
    """
    # pylint: disable=protected-access
    self._raw_credentials = data['path']


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_credential_loader
@pytest.mark.controller_credential_loader_credential_file
@pytest.mark.parametrize('data_path', _DATA_PATH)
def test_credential_load(data_path: Dict):
    """Test if the credentials are loaded correctly

    The test are performed loading credentials both via address and hostname

    Args:
        data_path (Dict): data to read
    """
    init_data = {
        'name': 'cred0',
        'type': 'cred-file',
        'path': data_path['credentials']
    }

    cf = CredFile(init_data)
    inv = read_yaml_file(data_path['inventory'])
    cf.load(inv)

    assert inv == read_yaml_file(data_path['results'])


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_credential_loader
@pytest.mark.controller_credential_loader_credential_file
@pytest.mark.parametrize('cred_file', _WRONG_CRED_FILE)
def test_wrong_cred_file_format(cred_file: str):
    """Test credential files with wrong formats

    Args:
        cred_file (str): credential file path
    """
    with pytest.raises(InventorySourceError):
        CredFile({'path': cred_file})


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_credential_loader
@pytest.mark.controller_credential_loader_credential_file
@pytest.mark.parametrize('data_path', [_DATA_PATH[0]])
def test_wrong_credentials(data_path: Dict):
    """Tests all the possible ways to missconfigure a CredFile

    Args:
        data_path (Dict): data to read
    """
    inv = read_yaml_file(data_path['inventory'])
    creds = read_yaml_file(data_path['credentials'])

    # missing 'path' field in input data
    with pytest.raises(InventorySourceError):
        CredFile({})

    # credential file doesn't exists
    with pytest.raises(InventorySourceError):
        CredFile({'path': 'wrong/path'})

    # invalid credential file
    with patch.multiple(CredFile, init=init_mock):

        # empty credentials
        cred_data = {
            'name': 'file0',
            'path': []
        }
        with pytest.raises(InventorySourceError):
            cr = CredFile(cred_data)
            cr.load(inv)

        # wrongly formatted credentials
        # missing 'namespace' field
        cred_data['path'] = [{'devices': []}]
        with pytest.raises(InventorySourceError):
            cr = CredFile(cred_data)
            cr.load(inv)

        # wrong namespace
        cred_data['path'] = [
            {
                'devices': [],
                'namespace': 'wrong_namespace'
            }
        ]
        with pytest.raises(InventorySourceError):
            cr = CredFile(cred_data)
            cr.load(inv)

        # credentials specified in both inventory and credential file
        cred_dev = creds[0]['devices'][0]
        cred_dev['username'] = 'user'
        for node in inv.values():
            if cred_dev.get('address') and \
                    cred_dev['address'] == node['address']:
                node['username'] = 'user'
            elif cred_dev.get('hostname') and \
                    cred_dev['hostname'] == node['hostname']:
                node['username'] = 'user'
        cred_data['path'] = creds
        with pytest.raises(InventorySourceError):
            cr = CredFile(cred_data)
            cr.load(inv)
        cred_dev.pop('username')

        # load an empty inventory
        cred_data['path'] = creds
        cr = CredFile(cred_data)
        cr.load({})

        # node with missing credentials
        creds[0]['devices'].pop()
        cred_data['path'] = creds
        with pytest.raises(InventorySourceError):
            cr = CredFile(cred_data)
            cr.load(inv)
