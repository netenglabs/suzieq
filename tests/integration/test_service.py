import os
import pytest
import yaml
from unittest.mock import MagicMock

from suzieq.poller.nodes import Node

from functools import partial

from tests.conftest import tables

# TODO
#  test changing nodelist in run
#  decompose all the aspects of service (maybe these are unit tests?)
#  test diff with data gathered twice (we have 2 sets of data, but aren't using the second set yet)
#  make sure we test all child classes
#  test writing to datastore? -- that seems big and lots of mocking
#  test node returns that take a long time -- test timeouts


@pytest.mark.service
@pytest.mark.parametrize('service', tables)
def test_process_services_end_to_end(service, init_services_default, event_loop, tmp_path):
    """This runs the main part of the run() method, but doesn't cover things like adding nodes"""
    service = [s for s in init_services_default if s.name == service][0]

    nodes = _create_node(service)
    assert len(nodes) > 0
    service.set_nodes(nodes)

    # replicating some of service.run to deconstruct
    service.nodelist = list(nodes.keys())
    outputs = event_loop.run_until_complete(service.gather_data())

    assert len(outputs) > 0

    results = {}
    for output in outputs:
        output = output[0]
        result = service.process_data(output)
        name = f"{output['namespace']}.{output['hostname']}"
        results[name] = []
        for res in result:
            results[name].append(res)

    processed = _get_processed_data(service)

    # this is the cod necessary to write out the data
    # file = tmp_path / f"{service.name}.yml"
    # print(f"writing to {file}")
    # file.write_text(yaml.dump(results))

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
                nodes.update(
                    {"{}.{}".format(node.namespace, node.hostname): node})
    return nodes


async def _create_exec_serivce(devtype, cmd, data, svc_defn):
    """code taken from exec_service in node.py"""

    use = svc_defn.get(devtype, {})
    assert use is not None

    if "copy" in use:
        use = svc_defn.get(use.get("copy"))

    defn_cmd = use.get("command", None)

    assert defn_cmd == cmd
    return data
