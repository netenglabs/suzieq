"""
Test the Inventory component functionalities
"""
# pylint: disable=redefined-outer-name

import asyncio
from typing import Callable, Dict, List
from unittest.mock import patch

import pytest
from suzieq.poller.worker.inventory.inventory import Inventory
from suzieq.poller.worker.nodes.node import Node
from tests.conftest import get_async_task_mock

sample_inventory = [
    {
        'address': '192.168.0.1',
        'username': 'username',
        'password': 'password',
        'port': 24,
        'transport': 'ssh',
        'devtype': 'linux',
        'namespace': 'test-namespace',
        'ssh_keyfile': 'tests/unit/poller/shared/sample_key',
        'jump_host': '//jump@host1',
        'jump_host_key_file': 'tests/unit/poller/shared/sample_key',
        'ignore_known_hosts': True,
        'passphrase': 'passphrase',
    },
    {
        'address': '192.168.0.2',
        'username': 'username',
        'password': 'password',
        'port': 25,
        'transport': 'ssh',
        'devtype': 'linux',
        'namespace': 'test-namespace',
        'ssh_keyfile': 'tests/unit/poller/shared/sample_key',
        'jump_host': '//jump@host2',
        'jump_host_key_file': 'tests/unit/poller/shared/sample_key',
        'ignore_known_hosts': True,
        'passphrase': 'passphrase',
    }
]


class SampleInventory(Inventory):
    """Sample Inventory subclass
    """
    async def _get_device_list(self) -> List[Dict]:
        return sample_inventory


def _init_inventory(add_task_fn: Callable = None, **kwargs):
    if not add_task_fn:
        add_task_fn = get_async_task_mock()
    return SampleInventory(add_task_fn,
                           **kwargs)


@pytest.fixture
@pytest.mark.asyncio
async def ready_inventory():
    """Fixture returning an already built inventory
    """
    inv = _init_inventory()
    with patch.multiple(Node, _init_ssh=get_async_task_mock(),
                        _fetch_init_dev_data=get_async_task_mock()):
        await inv.build_inventory()
    return inv


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
def test_inventory_init():
    """Test init of Inventory class
    """
    inventory_args = {
        'add_task_fn': get_async_task_mock(),
        'ssh_config_file': 'config/file',
        'connect_timeout': 30,
    }

    inv = _init_inventory(**inventory_args)

    for arg, arg_value in inventory_args.items():
        assert getattr(inv, arg) == arg_value


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
@pytest.mark.asyncio
@pytest.mark.parametrize("max_outstanding_cmds", [0, 5])
async def test_inventory_build(max_outstanding_cmds):
    """Test inventory build
    """
    inv = _init_inventory()
    inv._max_outstanding_cmd = max_outstanding_cmds

    with patch.multiple(Node, _init_ssh=get_async_task_mock(),
                        _fetch_init_dev_data=get_async_task_mock()):
        nodes = await inv.build_inventory()

    # Check if a semaphore with the proper initial value have been created
    assert inv._cmd_pacer, 'Command semaphore should be initialized'
    assert inv._cmd_pacer.max_cmds == max_outstanding_cmds

    # Check if nodes are registered in the inventory
    assert set(nodes) == set(inv.nodes)
    # Check if all the nodes have been registered
    assert len(inv.nodes) == 2
    # Check if all the parameters have been correctly set in the nodes
    for node in sample_inventory:
        key = f"{node['namespace']}.{node['address']}"
        invnode = nodes[key]
        assert node['namespace'] == invnode.nsname
        assert inv.connect_timeout == invnode.connect_timeout
        assert node['jump_host'].split("@")[1] == invnode.jump_host
        assert invnode.jump_host_key
        assert invnode._cmd_pacer == inv._cmd_pacer, \
            'Pacer not provided to nodes'

        for arg, arg_value in node.items():
            if arg in ['namespace', 'ssh_keyfile', 'jump_host',
                       'jump_host_key_file', 'passphrase']:
                continue
            assert arg_value == getattr(invnode, arg)


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
@pytest.mark.asyncio
async def test_get_node_callq(ready_inventory):
    """Test the get function returning the dictionary allowing
    to send command query
    """
    nodes = ready_inventory.nodes
    node_callq = ready_inventory.get_node_callq()
    # Check if all the nodes are in the node_callq
    assert len(node_callq) == len(nodes)
    for node in nodes:
        assert node_callq[node]['hostname'] == nodes[node].hostname
        assert node_callq[node]['postq'] == nodes[node].post_commands


@pytest.mark.poller
@pytest.mark.poller_unit_tests
@pytest.mark.poller_worker
@pytest.mark.poller_inventory
@pytest.mark.asyncio
async def test_node_scheduling(ready_inventory):
    """Test the schedule_nodes_run() function of inventory, checking if
    the function for adding tasks to the poller have been correctly called.
    """
    # Mock node run
    run_res = asyncio.Future()
    run_res.set_result(None)

    with patch.object(Node, 'run', return_value=run_res):
        await ready_inventory.schedule_nodes_run()

    # Check if add tasks have been called
    ready_inventory.add_task_fn.assert_called()
    # Check if there are running tasks
    assert ready_inventory.running_nodes
    assert len(ready_inventory.running_nodes) == len(sample_inventory)
    # Suppress never awaited alert
    await asyncio.wait(list(ready_inventory.running_nodes.values()))
