import pytest
import uvicorn
from multiprocessing import Process
import requests
import time
import random
import yaml

from tests.conftest import cli_commands, tables, setup_sqcmds
from tests import conftest
from suzieq.server.restServer import app

ENDPOINT = "http://localhost:8000/api/v1"

VERBS = ['show', 'summarize', 'assert', 'lpm', 'top']
FILTERS = ['', 'hostname=leaf01', 'namespace=dual-bgp',
           'address=10.0.0.1',
           'dest=172.16.2.104&src=172.16.1.101&namespace=dual-evpn',
           ]

# these service/verb pairs should return errors
BAD_VERBS = {'address/assert': 405, 'address/lpm': 404,
             'arpnd/assert': 405, 'arpnd/lpm': 404,
             'bgp/lpm': 404,
             'device/assert': 405, 'device/lpm': 404,
             'evpnVni/lpm': 404,
             'interface/lpm': 404,
             'lldp/assert': 405, 'lldp/lpm': 404,
             'mac/assert': 405, 'mac/lpm': 404,
             'mlag/assert': 405, 'mlag/lpm': 404,
             'ospf/lpm': 404,
             'path/assert': 405,
             'path/lpm': 404,
             'route/assert': 405,
             'vlan/assert': 405, 'vlan/lpm': 404,
             }

# these service/verb/filter tuples should return errors
BAD_FILTERS = {'lpm?hostname=leaf01': 404,
               'path/show?': 404, 'path/show?hostname=leaf01': 404,
               'path/show?namespace=dual-bgp': 404,
               'path/show?address=10.0.0.1': 404,
               'path/summarize?': 404, 'path/summarize?hostname=leaf01': 404,
               'path/summarize?namespace=dual-bgp': 404,
               'path/summarize?address=10.0.0.1': 404,
               'route/lpm?': 404, 'route/lpm?hostname=leaf01': 404,
               'route/lpm?namespace=dual-bgp': 404,
               'route/lpm?dest=172.16.2.104&src=172.16.1.101&namespace=dual-evpn': 404,
               }


def get(endpoint, command, verb, args):
    url = f"{endpoint}/{command}/{verb}?{args}"

    ret = requests.get(url)

    c_v = f"{command}/{verb}"
    c_v_f = f"{c_v}?{args}"
    if ret.status_code != 200:

        if c_v in BAD_VERBS:
            assert BAD_VERBS[c_v] == ret.status_code
        elif c_v_f in BAD_FILTERS:
            assert BAD_FILTERS[c_v_f] == ret.status_code
        else:
            ret.raise_for_status()
    else:
        assert c_v not in BAD_VERBS
        assert c_v_f not in BAD_FILTERS

    return ret.status_code


@pytest.mark.parametrize("command, verb, arg", [
    (cmd, verb, filter) for cmd in cli_commands
    for verb in VERBS for filter in FILTERS
])
def test_rest_commands(setup_nubia, start_server, command, verb, arg):
    get(ENDPOINT, command, verb, arg)


def create_config():
    # We need to create a tempfile to hold the config
    tmpconfig = conftest._create_context_config()

    tmpconfig['data-directory'] = './tests/data/multidc/parquet-out'
    r_int = random.randint(17, 2073)
    fname = f'/tmp/suzieq-cfg-{r_int}.yml'

    with open(fname, 'w') as f:
        f.write(yaml.dump(tmpconfig))
    return fname


@pytest.fixture(scope="session")
def start_server():
    app.cfg_file = create_config()

    Process(target=uvicorn.run,
            args=(app,),
            kwargs={'host': '0.0.0.0', 'port': 8000},
            daemon=True).start()
    time.sleep(0.3)


def test_bad_rest():
    pass
