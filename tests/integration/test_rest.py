import pytest
import random
import yaml
from fastapi.testclient import TestClient

from tests.conftest import cli_commands, tables, setup_sqcmds
from tests import conftest
from suzieq.server.restServer import app

ENDPOINT = "http://localhost:8000/api/v1"

VERBS = ['show', 'summarize', 'assert', 'lpm', 'unique']  # add 'top' when it's supported
FILTERS = ['', 'hostname=leaf01', 'namespace=ospf-ibgp',
           'address=10.127.1.2',
           'dest=172.16.2.104&src=172.16.1.101&namespace=ospf-ibgp',
           'columns=namespace',
           'view=latest',
           'address=10.127.1.2&view=all',
           'ipAddress=10.127.1.2',
           'vrf=default',
           'ipvers=v4',
           'macaddr=22:5c:65:2f:98:b6',
           'peer=eth1.2',
           'status=all',
           'vni=13',
           'mountPoint=/',
           'ifname=swp1',
           'type=ethernet',
           'state=up',
           'vlan=13',
           'remoteVtepIp=10.0.0.101',
           'bd=',
           'oif=eth1.4',
           'localOnly=True',
           'prefix=10.0.0.101/32',
           'protocol=bgp',
           'prefixlen=24',
           'service=device',
           'polled_neighbor=True',
           ]

# these should only succeed for the specific service/verb tuples
GOOD_FILTERS_FOR_SERVICE_VERB = {

    'address=10.127.1.2': ['route/lpm'],
    'address=10.127.1.2&view=all': ['route/lpm'],
    'bd=': ['mac/show'],
    'dest=172.16.2.104&src=172.16.1.101&namespace=ospf-ibgp':
    ['path/show', 'path/summarize'],
    'ifname=swp1': ['interface/show', 'interface/assert',
                    'lldp/show', 'ospf/show', 'ospf/assert'],
    'ipAddress=10.127.1.2': ['arpnd/show'],
    'ipvers=v4': ['address/show'],
    'localOnly=True': ['mac/show'],
    'macaddr=22:5c:65:2f:98:b6': ['arpnd/show', 'mac/show'],
    'mountPoint=/': ['fs/show'],
    'oif=eth1.4': ['arpnd/show'],
    'peer=eth1.2': ['bgp/show'],
    'polled_neighbor=True': ['topology/show', 'topology/summarize'],
    'prefix=10.0.0.101/32': ['route/show'],
    'prefixlen=24': ['route/show'],
    'protocol=bgp': ['route/show'],
    'service=device': ['sqPoller'],
    'remoteVtepIp=10.0.0.101': ['mac/show'],
    'state=up': ['interface/show', 'ospf/show'],
    'status=all': ['bgp/show'],
    'type=ethernet': ['interface/show'],
    'vlan=13': ['mac/show', 'vlan/show'],
    'vni=13': ['evpnVni/show'],
    'vrf=default': ['address/show', 'bgp/show', 'bgp/assert',
                    'ospf/assert', 'ospf/show',
                    'route/show', 'route/summarize', 'topology/show',
                    ]
}


# these service/verb pairs should return errors
BAD_VERBS = {'address/assert': 404, 'address/lpm': 404,
             'arpnd/assert': 404, 'arpnd/lpm': 404,
             'bgp/lpm': 404,
             'device/assert': 404, 'device/lpm': 404,
             'evpnVni/lpm': 404,
             'interface/lpm': 404,
             'lldp/assert': 404, 'lldp/lpm': 404,
             'mac/assert': 404, 'mac/lpm': 404,
             'mlag/assert': 404, 'mlag/lpm': 404,
             'ospf/lpm': 404,
             'path/assert': 404,
             'path/lpm': 404,
             'route/assert': 404,
             'topology/assert': 404,
             'topology/lpm': 404,
             'vlan/assert': 404, 'vlan/lpm': 404,
             }

# these are always bad filters for these verbs no matter the service
BAD_VERB_FILTERS = {
    'assert?columns=namespace': 405,
    'summarize?hostname=leaf01': 405,
    'summarize?columns=namespace': 405,
    'summarize?address=10.0.0.1': 405,
    'assert?address=10.0.0.1': 405,
    'assert?dest=172.16.2.104&src=172.16.1.101&namespace=ospf-ibgp': 405,
    'unique?hostname=leaf01': 405,
    'unique?': 405,
    'unique?view=latest': 405,
    'unique?namespace=ospf-ibgp': 405,
}

# these service/verb/filter tuples should return errors
#  because they are invalid filters for the service/verb combos
BAD_FILTERS = {
    'path/show?': 404, 'path/show?columns=namespace': 404,
    'path/show?hostname=leaf01': 404,
    'path/show?namespace=ospf-ibgp': 404,
    'path/show?address=10.0.0.1': 404,
    'path/summarize?': 404,
    'path/summarize?namespace=ospf-ibgp': 404,
    'path/summarize?address=10.0.0.1': 404,
    'path/summarize?hostname=leaf01': 404,
    'path/summarize?columns=namespace': 404,
    'path/summarize?view=latest': 404,
    'path/show?view=latest': 404,
    'path/unique?columns=namespace': 404,
    'route/lpm?': 404, 'route/lpm?columns=namespace': 404,
    'route/lpm?hostname=leaf01': 404,
    'route/lpm?namespace=ospf-ibgp': 404,
    'route/show?columns=namespace': 406,
    'route/lpm?view=latest': 404,
}


def get(endpoint, service, verb, args):
    url = f"{endpoint}/{service}/{verb}?{args}"

    client = TestClient(app)
    response = client.get(url)

    c_v = f"{service}/{verb}"
    c_v_f = f"{c_v}?{args}"
    v_f = f"{verb}?{args}"
    if response.status_code != 200:
        if c_v in BAD_VERBS:
            assert BAD_VERBS[c_v] == response.status_code, response.content.decode('utf8')
        elif c_v_f in BAD_FILTERS:
            assert BAD_FILTERS[c_v_f] == response.status_code, response.content.decode('utf8')
        elif v_f in BAD_VERB_FILTERS:
            assert BAD_VERB_FILTERS[v_f] == response.status_code, response.content.decode('utf8')
        elif args in GOOD_FILTERS_FOR_SERVICE_VERB:
            assert c_v not in GOOD_FILTERS_FOR_SERVICE_VERB[args]
            assert response.status_code == 405 or response.status_code == 404
        else:
            print(f" RESPONSE {response.status_code} {response.content.decode('utf8')}")
            response.raise_for_status()
    else:
        assert c_v not in BAD_VERBS
        assert c_v_f not in BAD_FILTERS
        assert v_f not in BAD_VERB_FILTERS
        if args in GOOD_FILTERS_FOR_SERVICE_VERB:
            assert c_v in GOOD_FILTERS_FOR_SERVICE_VERB[args]

        # make sure it's not empty when it shouldn't be    
        assert len(response.content.decode('utf8')) > 10
    return response.status_code


@pytest.mark.parametrize("service, verb, arg", [
    (cmd, verb, filter) for cmd in cli_commands
    for verb in VERBS for filter in FILTERS
])
def test_rest_services(setup_nubia, start_server, service, verb, arg):
    get(ENDPOINT, service, verb, arg)


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


def test_bad_rest():
    pass
