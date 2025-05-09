import os
import subprocess
from dataclasses import dataclass
from itertools import combinations
from tempfile import mkstemp
from time import sleep
from typing import Dict
from urllib.parse import parse_qs, urlparse

import pytest
import yaml
from requests.exceptions import ConnectionError

from suzieq.engines.rest.engineobj import SqRestEngine
from suzieq.shared.utils import load_sq_config
from tests.conftest import get_free_port, suzieq_rest_server_path


@dataclass
class SqContextMock:
    """ SqContext rest parameters mock
    """
    cfg: dict
    rest_api_key: str
    rest_transport: str
    rest_server_ip: str
    rest_server_port: int


@dataclass
class SqObjMock:
    """ class used to initialize the SqRestEngine.

    It contains the subset SqObject parameters needed by the rest engine to
    work
    """
    ctxt: SqContextMock
    start_time: str
    end_time: str
    hostname: str
    namespace: str
    view: str
    table: str
    columns: str


def validate_args(engine: SqRestEngine, params: Dict):
    """Validate the request is called with the right paramters

    Args:
        engine (SqRestEngine): the engine to test
        params (Dict): the parameters that must be set in the request query
    """
    def req_error(param: str, exp: str, got: str) -> str:
        return f'Wrong request {param}: expected {exp} - got {got}'

    try:
        # we expect the following function to raise a ConnectionError
        # exception since the server was not started
        engine._get_response('verb', **params)
        assert False, f'The request did not raise an exception for {params}'
    except ConnectionError as err:
        # get the request sent in the engine._get_response function
        url = urlparse(err.request.url)

        # check the path matches the internal variable parameters
        api_path = f'/api/v2/{engine.iobj.table}/verb'
        url_params = {
            # <param_name> : [<got>, <expected>]
            'ip': [url.hostname, engine.ctxt.rest_server_ip],
            'port': [url.port, engine.ctxt.rest_server_port],
            'transport': [url.scheme, engine.ctxt.rest_transport],
            'path': [url.path, api_path]
        }

        for param, values in url_params.items():
            assert values[0] == values[1], \
                req_error(param, values[1], values[0])

        # check query parameters
        url_query = parse_qs(url.query)
        for query_param, query_values in url_query.items():
            assert len(query_values) == 1, \
                f'Got more than 1 value for {query_param}'
            query_value = query_values[0]
            if query_param == 'access_token':
                # access_token needs a special validation
                assert query_value == engine.ctxt.rest_api_key, \
                    req_error(query_param, engine.ctxt.rest_api_key,
                              query_value)
            elif query_param in params:
                # check parameters set in the query
                assert params[query_param] == query_value, \
                    req_error(query_param, params[query_param], query_value)
            else:
                # check default parameters
                assert query_value == 'default', \
                    req_error(query_param, 'default', query_value)


@pytest.mark.engines
@pytest.mark.rest_engine
def test_request_params():
    """This test checks if parameters are set correctly in the request
    """
    ctxt = SqContextMock({}, 'key', 'http', 'rest-ip', 80)
    sqobj = SqObjMock(ctxt, 'default', 'default', 'default',
                      'default', 'default', 'default', 'default')
    engine = SqRestEngine(sqobj)
    # paramters which will override engine internal paramters
    sqobj_override_params = ['hostname', 'namespace', 'view']
    # other parameters
    other_params = ['other_param_0', 'other_param_1']

    testing_params = sqobj_override_params + other_params
    # try all combinations of params
    for n_sq_params in range(1, len(testing_params)+1):
        for sq_params in combinations(testing_params, n_sq_params):
            req_params = {p: 'override' for p in sq_params}
            validate_args(engine, req_params)


@pytest.mark.rest
@pytest.mark.skipif(not os.environ.get('TEST_SERVER', None),
                    reason='causes github action hang')
def test_server_cert():
    '''Can we can get a valid response with & without certificate'''

    # We need to change the port used to avoid conflicts
    config = {'data-directory': './tests/data/parquet',
              'temp-directory': '/tmp/suzieq',
              'logging-level': 'WARNING',
              'test_set': 'basic_dual_bgp',  # an extra field for testing
              'rest': {
                'rest-certfile': './tests/test_cert_CA/server-cert.pem',
                'rest-keyfile': './tests/test_cert_CA/server-key.pem',
                'API_KEY': '496157e6e869ef7f3d6ecb24a6f6d847b224ee4f',
                'logging-level': 'WARNING',
                'address': '0.0.0.0',
                'port': get_free_port(),
                'no-https': True,
                'log-stdout': True
              },
              'analyzer': {'timezone': 'GMT'},
              }

    def create_config(config):
        fd, tmpfname = mkstemp(suffix='.yml')
        f = os.fdopen(fd, 'w')
        f.write(yaml.dump(config))
        f.close()

        cfgfile = tmpfname
        sqcfg = load_sq_config(config_file=cfgfile)

        print(f'sqcfg: {sqcfg}')

        with open(cfgfile, 'w') as f:
            f.write(yaml.safe_dump(sqcfg))
        return sqcfg, cfgfile

    def open_rest_server(cfgfile):
        server_cmd_args = f'{suzieq_rest_server_path} -c {cfgfile}'.split()
        # pylint: disable=consider-using-with
        proc = subprocess.Popen(server_cmd_args)
        sleep(5)
        return proc

    def make_get_response_request(sqcfg):
        ctxt = SqContextMock(
            rest_api_key=sqcfg['rest']['API_KEY'],
            rest_transport='http' if sqcfg['rest']['no-https'] is True
                           else 'https',
            rest_server_ip=sqcfg['rest']['address'],
            rest_server_port=sqcfg['rest']['port'],
            cfg={'rest': sqcfg['rest']})

        sqobj = SqObjMock(ctxt, '', '', 'default',
                          'default', 'latest', 'device', 'default')

        engine = SqRestEngine(sqobj)
        try:
            response = engine._get_response('show')
            print(f'responsein test: {response}')
            return 200
        except Exception:
            return 400

    def close_session(proc, cfgfile):
        proc.kill()
        os.remove(cfgfile)

    # test with http verify None
    sqcfg, cfgfile = create_config(config)
    proc = open_rest_server(cfgfile)
    response = make_get_response_request(sqcfg)
    assert response == 200
    close_session(proc, cfgfile)

    # test with https verify None
    config['rest']['no-https'] = False
    sqcfg, cfgfile = create_config(config)
    proc = open_rest_server(cfgfile)
    response = make_get_response_request(sqcfg)
    assert response == 400
    close_session(proc, cfgfile)

    # test with https verify False
    config['rest']['cert-verify'] = False
    sqcfg, cfgfile = create_config(config)
    proc = open_rest_server(cfgfile)
    response = make_get_response_request(sqcfg)
    assert response == 200
    close_session(proc, cfgfile)

    # test with https verify True
    config['rest']['cert-verify'] = True
    sqcfg, cfgfile = create_config(config)
    proc = open_rest_server(cfgfile)
    response = make_get_response_request(sqcfg)
    assert response == 400
    close_session(proc, cfgfile)

    # test with https verify CA
    config['rest']['cert-verify'] =\
        './tests/test_cert_CA/ca-cert.pem'
    sqcfg, cfgfile = create_config(config)
    proc = open_rest_server(cfgfile)
    response = make_get_response_request(sqcfg)
    assert response == 200
    close_session(proc, cfgfile)
