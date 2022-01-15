import json
import os
import pytest
import yaml


@pytest.mark.service
def _test_init_with_default_config(init_services_default):
    with open(os.path.abspath(os.curdir) +
              '/tests/integration/services/samples/init.yml', 'r') as file:
        prev_results = yaml.safe_load(file)

    assert isinstance(init_services_default, list)
    for service in init_services_default:
        current_result = service.get_data()
        prev_result = json.loads(prev_results['tests'][service.name]['output'])
        assert current_result == prev_result


@pytest.mark.service
def _test_produce_current_json(tmp_path, init_services_default):
    """used strictly to produce the output that needs to be checked.

    this should only be necessary if you have on purpose changed configs
    and need to produce the output

    to use this, put a _ in front of each current test and remove the _ in
    front of this function
    pytest -mservice -s -n0
    """

    data = {}
    data['description'] = "output from running init_services"
    data['tests'] = {}
    for service in sorted(init_services_default, key=lambda x: x.name):
        data['tests'][service.name] = {}
        data['tests'][service.name]['service'] = service.name
        data['tests'][service.name]['output'] = json.dumps(service.get_data())

    file = tmp_path / "init.yml"
    print(f"writing to {file}")
    file.write_text(yaml.dump(data))
