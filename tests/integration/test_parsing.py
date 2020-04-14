import pytest
import yaml
import json
import os
import re

from suzieq.poller.services.svcparser import cons_recs_from_json_template

input_dir = '/tests/integration/parsing/input'
processed_dir = '/tests/integration/parsing/processed'

service_dir = 'config'

# TODO
#  collect output and compare


def _get_service_data(svc, device_type):
    with open(os.path.abspath(os.curdir) + intput_dir + '/' + svc + '.yml') as f:
        yml_inp = yaml.safe_load(f.read())
    raw_input = yml_inp.get('input', {}) \
        .get(device_type, '')
    return raw_input


def _get_service_def(svc, device_type):
    with open('{}/{}.yml'.format(service_dir, svc), 'r') as f:
        svcdef = yaml.safe_load(f.read())

    svcstr = svcdef.get('apply', {}) \
        .get(device_type, {}) \
        .get('normalize', '')
    return svcstr


def _get_test_data():
    tests = []
    for file in os.scandir(os.path.abspath(os.curdir) + intput_dir):
        if not file.path.endswith('.yml'):
            continue
        g = re.match('(.*)\.yml', file.name).groups()
        service = g[0]

        with open(file, 'r') as f:
            out = yaml.load(f.read(), Loader=yaml.BaseLoader)
            if 'input' in out:
                for dt in out['input']:
                    if service == 'ospfnbr' and dt == 'eos':
                        tests.append(pytest.param(service, dt,
                                                  marks=pytest.mark.xfail(reason='bug #69',
                                                                          raises=AttributeError)))
                    else:
                        tests.append([service, dt])
    return tests


def _get_processed_data(service, device_type):
    d = os.scandir(os.path.abspath(os.curdir) + processed_dir)
    file_name = f"{d}/{service}-{device_type}.yml"
    with open(file_name, 'r') as f:
        out = yaml.load(f.read)
    return out

@pytest.mark.parametrize("service, device_type",
                         _get_test_data())
def _test_service(service, device_type, tmp_path):
    svcstr = _get_service_def(service, device_type)
    assert svcstr
    sample_input = _get_service_data(service, device_type)
    assert sample_input
    created_records = cons_recs_from_json_template(svcstr, json.loads(sample_input))
    assert created_records
    assert len(created_records) > 0

    # this is the code necessary to write out the data
    file = tmp_path / f"{service}-{device_type}.yml"
    print(f"writing to {file}")
    file.write_text(yaml.dump(created_records))

    #processed_records = _get_processed_data(service, device_type)
    #assert processed_records == created_records
