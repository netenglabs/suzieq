import os
import pytest
import yaml
from unittest.mock import MagicMock
from collections import defaultdict
import asyncio

from suzieq.poller.nodes import Node

from functools import partial

from tests.conftest import tables

# TODO
#  decompose all the aspects of service (maybe these are unit tests?)
#  test diff with data gathered twice (we have 2 sets of data, but aren't using the second set yet)
#  make sure we test all child classes
#  test writing to datastore? -- that seems big and lots of mocking
#  test node returns that take a long time -- test timeouts


@pytest.mark.service
@pytest.mark.asyncio
@pytest.mark.parametrize('service', tables)
# this doesn't work anymore, it needs to change to fit the new way services work
# TODO: xfail
async def _test_process_services_end_to_end(service, init_services_default, event_loop, tmp_path):
    """This runs the main part of the run() method, but doesn't cover things like adding nodes"""
    service = [s for s in init_services_default if s.name == service][0]

    nodes = _create_node(service)
    assert len(nodes) > 0


    # taken from sq-poller
    node_callq = defaultdict(lambda: defaultdict(dict))

    node_callq.update({x: {'hostname': nodes[x].hostname,
                           'postq': nodes[x].post_commands}
                       for x in nodes})
    service.set_nodes(node_callq)
    print(node_callq)
    # replicating some of service.run to deconstruct
    assert False
    # right now it just hangs waiting for events. the queues
    # are not setup correctly yet
    await asyncio.gather(service.start_data_gather())

    _, outputs = await service.result_queue.get()
    assert len(outputs) > 1

    results = {}
    for output in outputs:
        output = output[0]
        result = service.process_data(output)
        name = f"{output['namespace']}.{output['hostname']}"
        results[name] = []
        for res in result:
            results[name].append(res)
    assert len(results) > 0
    processed = _get_processed_data(service)

    # this is the code necessary to write out the data
    file = tmp_path / f"{service.name}.yml"
    print(f"writing to {file}")
    file.write_text(yaml.dump(results))

    assert yaml.dump(results) == yaml.dump(processed)


def _get_processed_data(service):
    file = os.path.abspath(
        os.curdir) + f"/tests/data/basic_dual_bgp/processed/{service.name}.yml"

    with open(file, 'r') as f:
        out = yaml.load(f.read())
    assert len(out) > 0
    return out


def _create_node(service):
    nodes = {}
    file = os.path.abspath(
        os.curdir) + f"/tests/data/basic_dual_bgp/gathered/2/{service.name}-poller.yml"

    with open(file, 'r') as f:
        out = yaml.load(f.read(), Loader=yaml.BaseLoader)
        for n in out['output']:
            if len(n) > 0:
                node = MagicMock(spec=Node)
                node.namespace = n[0]['namespace']
                node.hostname = n[0]['hostname']
                node.exec_service = partial(
                    _create_exec_serivce, n[0]['devtype'],  n[0]['cmd'], n)
                node.post_commands = _create_post_commands
                nodes.update(
                    {"{}.{}".format(node.namespace, node.hostname): node})
    return nodes

def _create_post_commands(service_callback, svc_defn, cb_token):
    print(f"foo {service_callback}")

async def _create_exec_serivce(devtype, cmd, data, svc_defn):
    """code taken from exec_service in node.py"""

    use = svc_defn.get(devtype, {})
    assert use is not None

    if "copy" in use:
        use = svc_defn.get(use.get("copy"))

    defn_cmd = use.get("command", None)

    assert defn_cmd == cmd
    return data
