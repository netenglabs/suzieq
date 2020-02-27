import pytest
import os
import json, yaml
from unittest.mock import Mock

from suzieq.service import init_services

@pytest.mark.service
def test_init_with_default_config(event_loop):
    configs = os.path.abspath(os.curdir) + '/config/'
    schema = configs + 'schema/'
    mock_queue = Mock()
    with open(os.path.abspath(os.curdir) + '/tests/integration/services/samples/init.yml', 'r') as file:
        prev_results = yaml.load(file)

    services = event_loop.run_until_complete(init_services(configs, schema, mock_queue, True))
    assert isinstance(services, list)
    for service in services:
        current_result = service.get_data()
        prev_result = json.loads(prev_results['tests'][service.name]['output'])
        assert current_result == prev_result



@pytest.mark.service
def _test_produce_current_json(event_loop, tmp_path):
    """used strictly to produce the output that needs to be checked. this should only be necessary
    if you have on purpose changed configs and need to produce the output

    to use this, put a _ in front of each current test and remove the _ in front of this function
    """

    configs = os.path.abspath(os.curdir) + '/config/'
    schema = configs + 'schema/'
    mock_queue = Mock()
    services = event_loop.run_until_complete(init_services(configs, schema, mock_queue, True))
    assert isinstance(services, list)
    data = {}
    data['description'] = "output from running init_services"
    data['tests'] = {}
    for service in sorted(services, key=lambda x: x.name):
        data['tests'][service.name] = {}
        data['tests'][service.name]['service'] = service.name
        data['tests'][service.name]['output'] = json.dumps(service.get_data())

    file = tmp_path / f"init.yaml"
    print(f"writing to {file}")
    file.write_text(yaml.dump(data))
