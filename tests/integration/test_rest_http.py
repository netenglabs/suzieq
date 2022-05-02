from random import randint
from time import sleep
import subprocess
import os

import requests
import yaml
import pytest

from tests.conftest import create_dummy_config_file, suzieq_rest_server_path
from suzieq.shared.utils import load_sq_config


@pytest.mark.rest
@pytest.mark.skipif(not os.environ.get('TEST_SERVER', None),
                    reason='causes github action hang')
def test_server_exec():
    '''Can we can get a valid response with & without https'''

    # Generate a random port
    port = randint(9000, 10000)
    # We need to change the port used to avoid conflicts
    cfgfile = create_dummy_config_file()
    sqcfg = load_sq_config(config_file=cfgfile)

    if 'rest' not in sqcfg:
        sqcfg['rest'] = {'port': port}
    else:
        sqcfg['rest']['port'] = port

    with open(cfgfile, 'w') as f:
        f.write(yaml.safe_dump(sqcfg))

    server_cmd_args = f'{suzieq_rest_server_path} -c {cfgfile}'.split()
    # pylint: disable=consider-using-with
    proc = subprocess.Popen(server_cmd_args)

    # Try a request from the server
    sleep(5)
    resp = requests.get(f'https://localhost:{port}/api/docs', verify=False)
    assert(resp.status_code == 200)
    # Try a non-https request from the server
    sleep(5)
    try:
        resp = requests.get(f'http://localhost:{port}/api/docs', verify=False)
        assert(resp.status_code != 200)
    except requests.exceptions.ConnectionError:
        pass

    proc.kill()

    # Now test without https
    server_cmd_args = (
        f'{suzieq_rest_server_path} -c {cfgfile} --no-https'.split())
    # pylint: disable=consider-using-with
    proc = subprocess.Popen(server_cmd_args)

    # Try a request from the server
    sleep(5)
    resp = requests.get(f'http://localhost:{port}/api/docs', verify=False)
    assert(resp.status_code == 200)

    # Try a https request from the server
    sleep(5)
    try:
        resp = requests.get(f'https://localhost:{port}/api/docs', verify=False)
        assert(resp.status_code != 200)
    except requests.exceptions.ConnectionError:
        pass

    proc.kill()

    os.remove(cfgfile)
