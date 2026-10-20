"""Unit tests for PAN-OS arpnd/interfaces/lldp cleaners (synthetic data)."""
import os
import tempfile
from shutil import rmtree

import pytest

from suzieq.db.parquet.parquetdb import SqParquetDB
from suzieq.poller.worker.services.arpnd import ArpndService
from suzieq.poller.worker.services.interfaces import InterfaceService
from suzieq.poller.worker.services.lldp import LldpService
from suzieq.shared.schema import Schema, SchemaForTable
from suzieq.shared.utils import load_sq_config
from tests.conftest import create_dummy_config_file

MTU_TEXT = (
    "sw.dev.interface.config: { 'TCI': { 'hwaddr': 00:11:22:33:44:55, "
    "'mtu': 1500, }, 'ethernet1/1': { 'hwaddr': 00:11:22:33:44:56, "
    "'mtu': 9192, }, 'ethernet1/1.10': { 'comment': trust zone, "
    "link to core {A}, 'mtu': 1400, }, 'ethernet1/2': { }, "
    "'ae1': { 'mtu': 9000, }, }"
)


def _service(cls, name, keys):
    data_dir = tempfile.mkdtemp()
    cfg_file = create_dummy_config_file(datadir=data_dir)
    cfg = load_sq_config(config_file=cfg_file)
    schema_tab = SchemaForTable(name, Schema(cfg['schema-directory']))
    svc = cls(name, {}, 15, 'state', keys, [], schema_tab, None,
              SqParquetDB(cfg, None), 'forever')
    return svc, cfg_file, data_dir


@pytest.fixture
def services():
    """Provide arpnd/interfaces/lldp services backed by temp config"""
    created = {
        'arpnd': _service(ArpndService, 'arpnd',
                          ['namespace', 'hostname', 'ipAddress', 'oif']),
        'interfaces': _service(InterfaceService, 'interfaces',
                               ['namespace', 'hostname', 'ifname']),
        'lldp': _service(LldpService, 'lldp',
                         ['namespace', 'hostname', 'ifname']),
    }
    yield {k: v[0] for k, v in created.items()}
    for _, cfg_file, data_dir in created.values():
        os.remove(cfg_file)
        rmtree(data_dir)


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_panos_mtu_unquoted_comment():
    """MTU text with unquoted free-text comments must still parse"""
    assert InterfaceService._parse_panos_mtu(MTU_TEXT) == {
        'TCI': 1500, 'ethernet1/1': 9192, 'ethernet1/1.10': 1400,
        'ae1': 9000}


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_panos_interfaces_master_and_mtu(services):
    """ha/tap fwd values must not crash; mtu comes from the text output"""
    data = [
        {'_mtu_data': MTU_TEXT},
        {'ifname': 'ethernet1/1', 'type': '0', 'master': 'lr:LR-PROD',
         'speed': '10000', 'state': 'up', 'adminState': 'up'},
        {'ifname': 'ethernet1/1.10', 'master': 'vr:default'},
        {'ifname': 'ae1.193', 'master': 'lr:LR-PROD'},
        {'ifname': 'ha1-a', 'master': 'ha'},
        {'ifname': 'ethernet1/9', 'master': 'tap'},
        {'ifname': 'tunnel', 'master': 'N/A'},
    ]
    out = {x['ifname']: x for x in
           services['interfaces']._clean_panos_data(data, None)}
    assert out['ethernet1/1']['master'] == 'LR-PROD'
    assert out['ethernet1/1']['mtu'] == 9192
    assert out['ethernet1/1.10']['master'] == 'default'
    # subinterfaces inherit mtu/state from the physical parent
    assert out['ethernet1/1.10']['mtu'] == 9192
    assert out['ae1.193']['mtu'] == 9000
    assert out['ha1-a']['master'] == ''
    assert out['ethernet1/9']['master'] == ''
    assert out['tunnel']['master'] == 'default'


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_panos_arpnd_empty_and_missing_state(services):
    """Empty ND tables and entries without status are handled"""
    data = [
        {'ipAddress': '10.0.0.1', 'state': 'c'},
        {'ipAddress': '10.0.0.2', 'state': None},
        {'ipAddress': 'fe80::1', 'state': 'reachable'},
        {'ipAddress': '', 'state': ''},
        {},
    ]
    out = services['arpnd']._clean_panos_data(data, None)
    assert [x['ipAddress'] for x in out] == ['10.0.0.1', '10.0.0.2',
                                            'fe80::1']
    assert [x['state'] for x in out] == ['reachable', 'failed', 'reachable']


@pytest.mark.poller
@pytest.mark.poller_worker
@pytest.mark.poller_unit_tests
def test_panos_lldp_ports_without_neighbor(services):
    """Ports without neighbor are dropped; missing subtype tolerated"""
    data = [
        {'ifname': 'ethernet1/7', 'peerHostname': 'sw1',
         'peerIfname': 'Gi1/0/1', 'subtype': 'Interface Name'},
        {'ifname': 'ethernet1/8', 'peerHostname': '', 'peerIfname': ''},
        {'ifname': 'ethernet1/9', 'peerHostname': 'sw2',
         'peerIfname': 'Gi1/0/2'},
    ]
    out = services['lldp']._clean_panos_data(data, None)
    assert [x['ifname'] for x in out] == ['ethernet1/7', 'ethernet1/9']
    assert out[0]['subtype'] == 'interface name'
    # empty subtype is normalized by _common_cleaner
    assert out[1]['subtype'] == 'interface name'
