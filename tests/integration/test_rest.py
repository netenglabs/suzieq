import os
import json
import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from tests.conftest import cli_commands, create_dummy_config_file

from suzieq.restServer.query import app, get_configured_api_key, API_KEY_NAME, rest_main

ENDPOINT = "http://localhost:8000/api/v2"

VERBS = ['show', 'summarize', 'assert', 'lpm',
         'unique']  # add 'top' when it's supported

#
# The code logic is that you define all the filters you want to test in
# FILTERS. If a filter isn't in FILTERS, it isn't tested.
# Next:
#    * for every filter that has a good result against an object,
#      add it to the GOOD_FILTERS_FOR_SERVICE_VERB list
#    * for every filter that has a multiple values for the same key, add
#      a routine to test that the output contains all the requested values, &
#      add that routine to match against the filter to VALIDATE_OUTPUT_FILTER
#    * If a result is empty such as state=notConnected, add that object/verb
#      filter result to the GOOD_FILTER_EMPTY_RESULT_FILTER list. You can catch
#      an empty, but good result, because of the assertion error:
#      AssertionError: assert 2 > 10
#
FILTERS = ['',  # for vanilla commands without any filter
           'hostname=leaf01',
           'namespace=ospf-ibgp',
           'hostname=leaf01&hostname=spine01',
           'namespace=ospf-ibgp&namespace=ospf-single',
           'address=10.0.0.11',
           'dest=172.16.2.104&src=172.16.1.101&namespace=ospf-ibgp',
           'columns=namespace',
           'view=latest',
           'address=10.0.0.11&view=all',
           'ipAddress=10.0.0.11',
           'vrf=default',
           'ipvers=v4',
           'macaddr=44:39:39:ff:40:95',
           'macaddr=44:39:39:FF:40:95',
           'macaddr=4439.39FF.4095',
           'macaddr=4439.39ff.4095',
           'macaddr=44:39:39:ff:00:13&macaddr=44:39:39:ff:00:24',
           'peer=eth1.2',
           'vni=13',
           'vni=13%2024',
           'mountPoint=/',
           'ifname=swp1',
           'type=ethernet',
           'vlan=13',
           'remoteVtepIp=10.0.0.101',
           'bd=',
           'state=pass',
           'oif=eth1.4',
           'localOnly=True',
           'prefix=10.0.0.101/32',
           'protocol=bgp',
           'protocol=bgp&protocol=ospf',
           'prefixlen=24',
           'service=device',
           'polled=True',
           'usedPercent=8',
           'column=prefixlen',
           'status=pass',
           'status=fail',
           'status=all',
           'status=whatever',
           'vlanName=vlan13',
           'status=alive',
           'status=dead',
           'status=neverpoll',
           'state=up',
           'via=lldp&via=arpnd',
           'via=arpnd',
           'state=down',
           'state=notConnected',
           'state=active',
           'priVtepIp=10.0.0.112',
           'query_str=hostname%20==%20"leaf01"',
           'query_str=hostname=="leaf01"%20and%201000<mtu<2000'
           ]

# Valid filters for commands should be present in this list
# if a filter is valid for all commands and verbs, use ['all']
# if a filter is valid for all commands but only specific verbs,
# use ['all/<verb>']
# Everything else is assumed to be a failure i.e. response code != 200
GOOD_FILTERS_FOR_SERVICE_VERB = {
    '': ['all'],  # this is for all non-filtered requests
    'address=10.0.0.11': ['route/lpm'],
    'address=10.0.0.11&view=all': ['route/lpm'],
    'bd=': ['mac/show'],
    'hostname=leaf01&hostname=spine01': ['all'],
    'namespace=ospf-ibgp&namespace=ospf-single': ['all'],
    'namespace=ospf-ibgp': ['all'],
    'view=latest': ['all'],
    'columns=namespace': ['all'],
    'hostname=leaf01': ['all'],
    'dest=172.16.2.104&src=172.16.1.101&namespace=ospf-ibgp':
    ['path/show', 'path/summarize'],
    'ifname=swp1': ['interface/show', 'interface/assert',
                    'lldp/show', 'ospf/show', 'ospf/assert'],
    'ipAddress=10.0.0.11': ['arpnd/show'],
    'ipvers=v4': ['address/show'],
    'localOnly=True': ['mac/show'],
    'macaddr=44:39:39:ff:00:13': ['arpnd/show', 'mac/show'],
    'mountPoint=/': ['fs/show'],
    'oif=eth1.4': ['arpnd/show'],
    'peer=eth1.2': ['bgp/show'],
    'polled=True': ['topology/show'],
    'prefix=10.0.0.101/32': ['route/show'],
    'prefixlen=24': ['route/show'],
    'priVtepIp=10.0.0.112': ['evpnVni/show'],
    'protocol=bgp&protocol=ospf': ['route/show'],
    'protocol=bgp': ['route/show'],
    'service=device': ['sqPoller'],
    'remoteVtepIp=10.0.0.101': ['mac/show'],
    'state=up': ['interface/show'],
    'state=down': ['interface/show'],
    'state=notConnected': ['interface/show'],
    'state=Established': ['bgp/show'],
    'state=NotEstd': ['bgp/show'],
    'state=all': ['ospf/show'],
    'state=full': ['ospf/show'],
    'state=other': ['ospf/show'],
    'state=passive': ['ospf/show'],
    'type=ethernet': ['interface/show'],
    'usedPercent=8': ['fs/show'],
    'vlan=13': ['mac/show', 'vlan/show'],
    'vni=13': ['evpnVni/show'],
    'vni=13%2024': ['evpnVni/show'],
    'column=prefixlen': ['route/unique'],
    'vrf=default': ['address/show', 'bgp/show', 'bgp/assert',
                    'ospf/assert', 'ospf/show',
                    'route/show', 'route/summarize',
                    ],
    'status=pass': ['bgp/assert', 'evpnVni/assert', 'interfaces/assert',
                    'ospf/assert', 'sqpoller/show'],
    'status=fail': ['bgp/assert', 'evpnVni/assert', 'interfaces/assert',
                    'ospf/assert'],
    'status=all': ['bgp/assert', 'evpnVni/assert', 'interfaces/assert',
                   'ospf/assert'],
    'status=alive': ['device/show'],
    'status=dead': ['device/show'],
    'status=neverpoll': ['device/show'],
    'vlanName=vlan13': ['vlan/show'],
    'state=active': ['vlan/show'],
    'query_str=hostname%20==%20"leaf01"': ['all/show'],
    'query_str=hostname%20==%20"leaf01"': ['all/summarize'],
    'query_str=hostname%20==%20"leaf01"': ['all/unique'],
    'via=arpnd': ['topology/show'],
    'via=lldp&via=arpnd': ['topology/show'],
    'macaddr=44:39:39:ff:00:13&macaddr=44:39:39:ff:00:24': ['mac/show'],
    'macaddr=4439.39ff.4095': ['mac/show'],
    'macaddr=4439.39FF.4095': ['mac/show'],
    'macaddr=44:39:39:FF:40:95': ['mac/show'],
    'macaddr=44:39:39:ff:40:95': ['mac/show'],
    'query_str=hostname=="leaf01"%20and%201000<mtu<2000':
    ['interface/show', 'interface/summaeize', 'interface/unique']
}

GOOD_FILTER_EMPTY_RESULT_FILTER = [
    'sqpoller/show?status=fail',
    'ospf/assert?status=fail',
    'evpnVni/assert?status=fail',
    'interface/show?state=notConnected',
    'device/show?status=neverpoll',
    'device/show?status=dead',
]

####
# Validation functions: Needed especially for filters that specify multiple
# values for a single key.
####


def _validate_hostname_output(json_out, service, verb):
    if verb == "summarize":
        return True
    if service in ["mac", "vlan", "mlag", "evpnVni"]:
        # MAC addr is not present on spines
        assert (set([x['hostname'] for x in json_out]) == set(['leaf01']))
    else:
        assert (set([x['hostname'] for x in json_out])
                == set(['leaf01', 'spine01']))


def _validate_namespace_output(json_out, service, verb):
    if verb == "summarize":
        # summarize output has namespace as a key
        if service in ["bgp", "evpnVni", "devconfig", "mlag"]:
            assert(set(json_out.keys()) == set(['ospf-ibgp']))
        else:
            assert (set(json_out.keys()) == set(['ospf-ibgp', 'ospf-single']))
    else:
        if service in ["bgp", "evpnVni", "devconfig", "mlag"]:
            assert(set([x['namespace']
                   for x in json_out]) == set(['ospf-ibgp']))
        else:
            assert (set([x['namespace'] for x in json_out])
                    == set(['ospf-ibgp', 'ospf-single']))


def _validate_route_protocol(json_out, service, verb):
    assert (set([x['protocol'] for x in json_out]) == set(['ospf', 'bgp']))


def _validate_macaddr_output(json_out, service, verb):
    assert (set([x['macaddr'] for x in json_out])
            == set(['44:39:39:ff:00:13', '44:39:39:ff:00:24']))


VALIDATE_OUTPUT_FILTER = {
    'namespace=ospf-ibgp&namespace=ospf-single': _validate_namespace_output,
    'hostname=leaf01&hostname=spine01': _validate_hostname_output,
    'protocol=bgp&protocol=ospf': _validate_route_protocol,
    'macaddr=44:39:39:ff:00:13&macaddr=44:39:39:ff:00:24':
    _validate_macaddr_output,
}

####
# Test functions start
####


def get(endpoint, service, verb, args):
    api_key = get_configured_api_key()
    url = f"{endpoint}/{service}/{verb}?{args}"

    client = TestClient(app)
    response = client.get(url, headers={API_KEY_NAME: api_key})

    c_v = f"{service}/{verb}"
    c_v_f = f"{c_v}?{args}"
    v_f = f"{verb}?{args}"

    argval = GOOD_FILTERS_FOR_SERVICE_VERB.get(args, [])

    if response.status_code != 200:
        if c_v in argval or argval == ['all']:
            assert(False,
                   f"{c_v_f} should not be in good responses list")
    else:
        if c_v in argval or argval == ['all']:
            if c_v_f not in GOOD_FILTER_EMPTY_RESULT_FILTER:
                assert len(response.content.decode('utf8')) > 10
            else:
                assert len(response.content.decode('utf8')) == 2
        elif argval[0].split('/')[0] == "all":
            match_verb = argval[0].split('/')[1]
            assert (match_verb == verb,
                    f"Unable to match good result for {c_v_f}")

        if c_v_f not in GOOD_FILTER_EMPTY_RESULT_FILTER:
            if args in VALIDATE_OUTPUT_FILTER:
                VALIDATE_OUTPUT_FILTER[args](response.json(), service, verb)
            else:
                assert len(response.content.decode('utf8')) > 10
        else:
            assert len(response.content.decode('utf8')) == 2

    return response.status_code


@ pytest.mark.rest
@ pytest.mark.parametrize("service, verb, arg", [
    (cmd, verb, filter) for cmd in cli_commands
    for verb in VERBS for filter in FILTERS
])
def test_rest_services(app_initialize, service, verb, arg):
    get(ENDPOINT, service, verb, arg)


@pytest.fixture()
def app_initialize():
    from suzieq.restServer.query import app_init

    cfgfile = create_dummy_config_file(
        datadir='./tests/data/multidc/parquet-out')
    app_init(cfgfile)
    yield
    os.remove(cfgfile)


# The basic test harness for fastapi doesn't really start a server
# so we need to test this separately. xdist tries to run tests in parallel
# which screws things up. So, we run server with & without https sequentially
# For some reason, putting the no_https in a for loop didn't work either
@pytest.mark.rest
def test_rest_server():
    from multiprocessing import Process
    from time import sleep
    import requests

    cfgfile = create_dummy_config_file(
        datadir='./tests/data/multidc/parquet-out')

    server = Process(target=rest_main, args=(cfgfile, True))
    server.start()
    assert (server.is_alive())
    sleep(1)
    assert (server.is_alive())
    assert(requests.get('http://localhost:8000/api/docs'))
    server.terminate()
    server.join()

    server = Process(target=rest_main, args=(cfgfile, False))
    server.start()
    assert (server.is_alive())
    sleep(1)
    assert (server.is_alive())
    assert (requests.get("https://localhost:8000/api/docs", verify=False))
    server.terminate()
    server.join()

    os.remove(cfgfile)
