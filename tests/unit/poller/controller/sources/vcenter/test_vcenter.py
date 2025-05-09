import pytest
from unittest.mock import MagicMock, patch
from suzieq.poller.controller.source.vcenter import Vcenter
from tests.unit.poller.shared.utils import get_src_sample_config
from pyVmomi import vim, vmodl


@pytest.fixture(scope="function", autouse=True)
def service_instance():
    mock_si = MagicMock()
    mock_content = MagicMock()
    mock_si.RetrieveContent.return_value = mock_content
    mock_content.viewManager.CreateContainerView.return_value = MagicMock()

    mock_content.propertyCollector.RetrievePropertiesEx = MagicMock()
    mock_custom_field_def1 = vim.CustomFieldDef(name="suzieq", key=101)
    mock_custom_field_def2 = vim.CustomFieldDef(name="monitoring", key=102)
    mock_content.customFieldsManager.field = [mock_custom_field_def1, mock_custom_field_def2]

    with patch('suzieq.poller.controller.source.vcenter.SmartConnect', return_value=mock_si), \
         patch('suzieq.poller.controller.source.vcenter.vmodl.query.PropertyCollector.ObjectSpec', return_value=MagicMock()), \
         patch('suzieq.poller.controller.source.vcenter.vmodl.query.PropertyCollector.FilterSpec', return_value=MagicMock()):
        yield mock_content

@pytest.mark.controller_source
@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.poller_unit_tests
@pytest.mark.controller_unit_tests
@pytest.mark.controller_source_vcenter
@pytest.mark.asyncio
async def test_get_inventory_list_successful(service_instance):
    """Test successful retrieval of VM inventory."""

    service_instance.propertyCollector.RetrievePropertiesEx.return_value = vim.PropertyCollector.RetrieveResult(
        objects=[
            vim.ObjectContent(
                obj=vim.VirtualMachine("vm-1234"),
                propSet=[
                    vmodl.DynamicProperty(name='name', val='multiple-attr-vm'),
                    vmodl.DynamicProperty(name='guest.ipAddress', val='192.168.1.1'),
                    vmodl.DynamicProperty(name='customValue', val=vim.ArrayOfCustomFieldValue([vim.CustomFieldStringValue(key=102, value='true'), vim.CustomFieldStringValue(key=101, value='true')]))
                ]
            ),
            vim.ObjectContent(
                obj=vim.VirtualMachine("vm-2345"),
                propSet=[
                    vmodl.DynamicProperty(name='name', val='single-attr-vm'),
                    vmodl.DynamicProperty(name='guest.ipAddress', val='192.168.1.2'),
                    vmodl.DynamicProperty(name='customValue', val=vim.ArrayOfCustomFieldValue([vim.CustomFieldStringValue(key=101, value='true')]))
                ]
            ),
            vim.ObjectContent(
                obj=vim.VirtualMachine("vm-3456"),
                propSet=[
                    vmodl.DynamicProperty(name='name', val='no-attr-vm'),
                    vmodl.DynamicProperty(name='guest.ipAddress', val='192.168.1.3'),
                    vmodl.DynamicProperty(name='customValue', val=[])
                ]
            ),
            vim.ObjectContent(
                obj=vim.VirtualMachine("vm-4567"),
                propSet=[
                    vmodl.DynamicProperty(name='name', val='no-ip-vm'),
                    vmodl.DynamicProperty(name='guest.ipAddress', val=''),
                    vmodl.DynamicProperty(name='customValue', val=vim.ArrayOfCustomFieldValue([vim.CustomFieldStringValue(key=101, value='true')]))
                ]
            )
        ]
    )

    vc = Vcenter(get_src_sample_config('vcenter'))
    inventory = await vc.get_inventory_list()

    # Asserts to verify the correct functionality
    expected_inventory = {
        'multiple-attr-vm': '192.168.1.1',
        'single-attr-vm': '192.168.1.2',
    }
    assert inventory == expected_inventory, "Inventory should match expected output including multiple attributes and VM details"
