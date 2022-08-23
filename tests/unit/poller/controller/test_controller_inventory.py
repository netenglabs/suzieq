from typing import Dict
import pytest
from suzieq.shared.utils import get_sensitive_data
from suzieq.poller.controller.utils.inventory_utils import (
    read_inventory, validate_raw_inventory,
    copy_inventory_item)
from suzieq.shared.exceptions import InventorySourceError
from tests.unit.poller.shared.utils import read_yaml_file
# pylint: disable=redefined-outer-name

_INVENTORY_PATH = ['tests/unit/poller/controller/data/inventory.yaml']
_EXP_INVENTORY_PATH = ['tests/unit/poller/controller/data/exp-inventory.yaml']


@pytest.fixture
def default_inventory() -> Dict:
    """Return default inventory

    Yields:
        Dict: default inventory
    """
    inventory = {
        'namespaces': [{
            'name': 'ns0',
            'source': 'src0'}],
        'devices': [{'name': 'dev0'}],
        'auths': [{'name': 'auth0'}],
        'sources': [{
            'name': 'src0',
            'hosts': [{'url': 'ssh://vagrant@10.255.2.250:22'}]
        }]
    }
    yield inventory


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
@pytest.mark.parametrize('inv_path', _INVENTORY_PATH)
@pytest.mark.parametrize('exp_inv_path', _EXP_INVENTORY_PATH)
def test_read_valid_inventory(inv_path: str, exp_inv_path: str):
    """Test if an inventory is read correctly

    Args:
        inv_path (str): path to a valid inventory
        exp_inv_path (str): path to the expected inventory output
    """

    exp_inventory = read_yaml_file(exp_inv_path)

    inventory = read_inventory(inv_path)
    assert inventory == exp_inventory


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
@pytest.mark.parametrize('field', ['namespaces', 'sources'])
def test_mandatory_fields(field: str, default_inventory):
    """Test that mandatory fields are correctly validated

    Args:
        field (str): field to check
    """
    inventory = default_inventory
    # empty field

    old_field = inventory.pop(field)
    inventory[field] = []
    with pytest.raises(InventorySourceError,
                       match=r".*{field}: ensure this value has at least 1 "
                       "items".format(field=field)):
        validate_raw_inventory(inventory)

    inventory.pop(field)

    with pytest.raises(InventorySourceError,
                       match=r".* {field}: field required"
                       .format(field=field)):
        validate_raw_inventory(inventory)

    inventory[field] = old_field
    validate_raw_inventory(inventory)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
@pytest.mark.parametrize('field',
                         ['namespaces', 'sources', 'devices', 'auths'])
def test_inventory_fields_validation(field, default_inventory):
    """Test the validation of the inventory
    """
    inventory = default_inventory

    # item is not a list
    old_value, inventory[field] = inventory[field], 'not-a-list'

    with pytest.raises(InventorySourceError,
                       match=r'.*{field}: value is not a valid list'
                       .format(field=field)):
        validate_raw_inventory(inventory)

    # subitem is not a dictionary
    inventory[field] = ['not-a-dict']
    with pytest.raises(InventorySourceError,
                       match=r'.*{field}.0: value is not a valid dict'
                       .format(field=field)):
        validate_raw_inventory(inventory)

    if field == 'namespaces':
        # missing 'name','source' fields
        for f in ['name', 'source']:
            inventory[field] = [old_value[0].copy()]
            inventory[field][0].pop(f)
            with pytest.raises(InventorySourceError,
                               match=r".*{f}: field required"
                               .format(f=f)):
                validate_raw_inventory(inventory)

        # invalid 'name'
        for f in ['source', 'device', 'auth']:
            inventory[field] = [old_value[0].copy()]
            inventory[field][0][f] = 'not-a-name'
            with pytest.raises(InventorySourceError,
                               match=r".* No {f} called 'not-a-name'"
                               .format(f=f)):
                validate_raw_inventory(inventory)

    else:
        # field without a name
        inventory[field] = [{'not-name': 'name'}]
        with pytest.raises(InventorySourceError,
                           match=r".*name: field required"):
            validate_raw_inventory(inventory)

        # not unique name
        inventory[field] = [{'name': 'not-unique'}, {'name': 'not-unique'}]
        if field == 'sources':
            _ = [i.update({'hosts': [{'url': 'ssh://vagrant@10.255.2.250:22'}]})
                 for i in inventory[field]]
        with pytest.raises(InventorySourceError,
                           match=f'{field}.not-unique is not unique'):
            validate_raw_inventory(inventory)

        # wrong copy name
        inventory[field] = [{'name': 'a-name', 'copy': 'not-a-name'}]
        with pytest.raises(InventorySourceError,
                           match=f"copy value must be a 'name' "
                           f"of an already defined {field}: not-a-name not "
                           "found"):
            validate_raw_inventory(inventory)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
def test_detected_unknown_field(default_inventory):
    """test if an unknown field is detected"""
    inventory = default_inventory
    inventory['not-valid'] = []

    with pytest.raises(InventorySourceError,
                       match=r".*not-valid: extra fields not permitted"):
        validate_raw_inventory(inventory)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
def test_empty_inventory():
    """Test if an empty inventory is detected
    """
    inventory = {}
    with pytest.raises(InventorySourceError,
                       match='The inventory is empty'):
        validate_raw_inventory(inventory)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
def test_copy_function():
    """Test that using the 'copy' parameter returns the correct result
    """

    exp_result = {'src0':
                  {'name': 'src0', 'value1': 'old', 'value2': 'stable'},
                  'src1':
                  {'name': 'src1', 'value1': 'new', 'value2': 'stable'}}

    orig = {'name': 'src0', 'value1': 'old', 'value2': 'stable'}
    dest = {'name': 'src1', 'value1': 'new', 'copy': 'src0'}

    result = copy_inventory_item(orig, dest)
    assert orig == exp_result['src0']
    assert result == exp_result['src1']


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
def test_get_sensitive_data(monkeypatch):
    """Test sensitive parameters are correctly collected
    """
    sens_value = 'sensitive-value'

    # 'env' value
    env_var_name = 'ENV_VAR'
    monkeypatch.setenv(env_var_name, sens_value)
    assert sens_value == get_sensitive_data(f'env:{env_var_name}')

    # 'plain' value
    assert sens_value == get_sensitive_data(f'plain:{sens_value}')
    assert sens_value == get_sensitive_data(sens_value)

    monkeypatch.setattr('getpass.getpass', lambda x: sens_value)
    assert sens_value == get_sensitive_data('ask')


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_inventory
def test_device_validations(default_inventory):
    inventory = default_inventory

    # Invalid jump-host
    inventory['devices'][0]['jump-host'] = 'scheme://user@192.0.1.0:2222'
    with pytest.raises(InventorySourceError,
                    match="format username@jumphost\\[:port\\] required"):
        validate_raw_inventory(inventory)
