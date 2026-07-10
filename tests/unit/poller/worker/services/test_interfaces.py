import os
import tempfile
from shutil import rmtree

import pytest

from suzieq.db.parquet.parquetdb import SqParquetDB
from suzieq.poller.worker.services.interfaces import InterfaceService
from suzieq.shared.schema import Schema, SchemaForTable
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file


JUNOS_TYPE_LOGIC_CASES = [
    ('some-type', 'Ethernet', 'ethernet', 'linktype_overrides_str'),
    (['some-type'], ['Ethernet'], 'ethernet', 'linktype_overrides_list'),
    ('Ethernet', '', 'ethernet', 'type_str_linktype_empty'),
    (['Ethernet'], '', 'ethernet', 'type_list_linktype_empty'),
    ('', 'Ethernet', 'ethernet', 'type_empty_linktype_str'),
    ('', ['Ethernet'], 'ethernet', 'type_empty_linktype_list'),
    ('', '', 'internal', 'both_empty'),
    ([''], '', 'internal', 'list_empty_string'),
    ([None], '', 'internal', 'list_none'),
    ([], '', 'internal', 'empty_list'),
    (None, '', 'internal', 'none_input'),
    (['Ethernet', 'Other'], '', 'ethernet', 'list_multiple_1'),
    (['First', 'Second', 'Third'], '', 'first', 'list_multiple_2'),
]


@pytest.fixture
def interface_service():
    """Provide an InterfaceService instance backed by temp config"""
    data_dir = tempfile.mkdtemp()
    cfg_file = create_dummy_config_file(datadir=data_dir)
    cfg = load_sq_config(config_file=cfg_file)
    schema = Schema(cfg['schema-directory'])
    schema_tab = SchemaForTable('interfaces', schema)
    db_access = SqParquetDB(cfg, None)
    keys = ['namespace', 'hostname', 'ifname']
    service = InterfaceService('interfaces', {}, 15, 'state',
                               keys, [], schema_tab, None,
                               db_access, 'forever')
    yield service
    os.remove(cfg_file)
    rmtree(data_dir)

@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
@pytest.mark.parametrize("type_val,linktype_val,expected,test_id", JUNOS_TYPE_LOGIC_CASES)
def test_junos_type_field_logic(interface_service, type_val, linktype_val, expected, test_id):
    """Test the type field resolution logic in _clean_junos_data"""
    processed = [{
        'ifname': f'ge-0/0/0-{test_id}',
        'type': type_val,
        '_linkLevelType': linktype_val,
        'mtu': 1514,
        'macaddr': '00:11:22:33:44:55',
        'speed': '1000mbps',
        'statusChangeTimestamp': 0,
        '_logIf': []
    }]
    raw_data = [{'timestamp': 1677564128000}]
    
    cleaned = interface_service._clean_junos_data(processed, raw_data)
    assert cleaned[0]['type'] == expected


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_ex9208_vrf_with_list_type(interface_service):
    """Original bug: EX9208 14.2R8.4 returns VRF type as list"""
    processed = [{
        'ifname': 'blue1',
        'type': ['Virtual-router'],
        '_linkLevelType': '',
        '_interfaceList': ['ge-0/0/0.0', 'ge-0/0/1.0'],
        'mtu': 1500,
        'macaddr': '',
        'statusChangeTimestamp': 0
    }]
    raw_data = [{'timestamp': 1677564128000}]
    
    cleaned = interface_service._clean_junos_data(processed, raw_data)
    
    assert cleaned[0]['type'] == 'vrf'
    assert cleaned[0]['state'] == 'up'
    assert cleaned[0]['adminState'] == 'up'


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_qfx_ethernet_with_linktype(interface_service):
    """QFX devices typically provide _linkLevelType"""
    processed = [{
        'ifname': 'xe-0/0/0',
        'type': ['Interface'],
        '_linkLevelType': ['Ethernet'],
        'mtu': 1514,
        'macaddr': '00:11:22:33:44:55',
        'speed': '10Gbps',
        'statusChangeTimestamp': 0,
        '_logIf': []
    }]
    raw_data = [{'timestamp': 1677564128000}]
    
    cleaned = interface_service._clean_junos_data(processed, raw_data)
    
    assert cleaned[0]['type'] == 'ethernet'
    assert cleaned[0]['speed'] == 10000


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_mx_irb_interface(interface_service):
    """MX devices with IRB interfaces"""
    processed = [{
        'ifname': 'irb.100',
        'type': 'irb',
        '_linkLevelType': '',
        'mtu': 1500,
        'macaddr': '00:11:22:33:44:55',
        'speed': 'Unlimited',
        'statusChangeTimestamp': 0,
        '_logIf': []
    }]
    raw_data = [{'timestamp': 1677564128000}]
    
    cleaned = interface_service._clean_junos_data(processed, raw_data)
    
    assert cleaned[0]['type'] == 'vlan'


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_mixed_string_and_list_types(interface_service):
    """Multiple interfaces with different type formats"""
    processed = [
        {
            'ifname': 'ge-0/0/0',
            'type': 'Ethernet',
            '_linkLevelType': '',
            'mtu': 1514,
            'macaddr': '00:11:22:33:44:55',
            'speed': '1000mbps',
            'statusChangeTimestamp': 0,
            '_logIf': []
        },
        {
            'ifname': 'ge-0/0/1',
            'type': ['Ethernet'],
            '_linkLevelType': '',
            'mtu': 1514,
            'macaddr': '00:11:22:33:44:66',
            'speed': '1000mbps',
            'statusChangeTimestamp': 0,
            '_logIf': []
        },
        {
            'ifname': 'vrf-blue',
            'type': ['Virtual-router'],
            '_linkLevelType': '',
            '_interfaceList': ['ge-0/0/0.0'],
            'mtu': 1500,
            'macaddr': '',
            'statusChangeTimestamp': 0
        }
    ]
    raw_data = [{'timestamp': 1677564128000}]
    
    cleaned = interface_service._clean_junos_data(processed, raw_data)
    
    assert cleaned[0]['type'] == 'ethernet'
    assert cleaned[1]['type'] == 'ethernet'
    assert cleaned[2]['type'] == 'vrf'
