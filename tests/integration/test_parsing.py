import pytest
import yaml
import json
import os
import re

from suzieq.poller.services.svcparser import cons_recs_from_json_template

samples_dir = '/tests/integration/parsing/input'
service_dir = 'config'

# TODO
#  how do I deal with xfail in the version that reads tests from directory
#  change how it deals with data, so the test isn't so long
#  collect output and compare


def _get_service_data(svc, device_type):
    with open(os.path.abspath(os.curdir) + samples_dir + '/' + svc + '.yml') as f:
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
    for file in os.scandir(os.path.abspath(os.curdir) + samples_dir):
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


@pytest.mark.parametrize("service, device_type",
                         _get_test_data())
def test_service(service, device_type):
    svcstr = _get_service_def(service, device_type)
    assert svcstr
    sample_input = _get_service_data(service, device_type)
    assert sample_input
    records = cons_recs_from_json_template(svcstr, json.loads(sample_input))
    assert records
    assert len(records) > 0
