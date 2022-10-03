import inspect
import json
import os
import warnings
from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic.fields import ModelField
from suzieq.restServer import query
from suzieq.restServer.query import (API_KEY_NAME, CommonExtraVerbs,
                                     CommonVerbs, NetworkVerbs, RouteVerbs,
                                     app, cleanup_verb, get_configured_api_key)
from suzieq.sqobjects import get_sqobject
from suzieq.sqobjects.basicobj import SqObject
from tests.conftest import cli_commands, create_dummy_config_file, TABLES

ENDPOINT = "http://localhost:8000/api/v2"

VERBS = ['show', 'summarize', 'assert', 'lpm', 'top',
         'unique', 'find', 'describe']

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
           'address=172.16.1.101',
           'vrf=default',
           'ipvers=v4',
           'macaddr=44:39:39:ff:40:95',
           'macaddr=44:39:39:FF:40:95',
           'macaddr=4439.39FF.4095',
           'macaddr=4439.39ff.4095',
           'macaddr=44:39:39:ff:00:13&macaddr=44:39:39:ff:00:24',
           'peer=eth1.2',
           'vni=13',
           'vni=13&vni=24',
           'mountPoint=/',
           'ifname=swp1',
           'type=ethernet',
           'vlan=13',
           'remoteVtepIp=10.0.0.101',
           'bd=',
           'state=pass',
           'oif=eth1.4',
           'local=True',
           'prefix=10.0.0.101/32',
           'protocol=bgp',
           'protocol=bgp&protocol=ospf',
           'prefixlen=24',
           'service=device',
           'polled=True',
           'usedPercent=8',
           'column=prefixlen',
           'result=pass',
           'result=fail',
           'result=all',
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
           'query_str=hostname=="leaf01"%20and%201000<mtu<2000',
           'what=mtu',
           'what=numChanges',
           'what=uptime',
           'what=prefixLen',
           'columns=vrf',
           'pollExcdPeriodCount=!0',
           'pollExcdPeriodCount=0',
           ]

# Valid filters for commands should be present in this list
# if a filter is valid for all commands and verbs, use ['all']
# if a filter is valid for all commands but only specific verbs,
# use ['all/<verb>']
# Everything else is assumed to be a failure i.e. response code != 200
NOT_SUMMARIZE = ['all/top', 'all/unique', 'all/show',
                 'route/lpm', 'all/assert', 'network/find']
NOT_UNIQUE = ['all/top', 'all/summarize', 'all/show',
              'route/lpm', 'all/assert', 'network/find']
NOT_SUMMARIZE_OR_DESCRIBE = ['all/describe'] + NOT_SUMMARIZE
GOOD_FILTERS_FOR_SERVICE_VERB = {
    '': ['all'],  # this is for all non-filtered requests
    'address=10.0.0.11': ['route/lpm'],
    'address=10.0.0.11&view=all': ['route/lpm'],
    'address=172.16.1.101': ['network/find'],
    'bd=': ['mac/show'],
    'hostname=leaf01&hostname=spine01': NOT_UNIQUE,
    'hostname=leaf01&hostname=spine01&columns=hostname': ['all/unique'],
    'namespace=ospf-ibgp&namespace=ospf-single': NOT_UNIQUE,
    'namespace=ospf-ibgp&namespace=ospf-single&columns=namespace':
    ['all/unique'],
    'namespace=ospf-ibgp': NOT_UNIQUE,
    'namespace=ospf-ibgp&columns=namespace': ['all/unique'],
    'view=latest': ['all'],
    'columns=namespace': NOT_SUMMARIZE_OR_DESCRIBE,
    'hostname=leaf01': NOT_UNIQUE,
    'hostname=leaf01&columns=hostname': ['all/unique'],
    'dest=172.16.2.104&src=172.16.1.101&namespace=ospf-ibgp':
    ['path/show', 'path/summarize'],
    'ifname=swp1': ['interface/show', 'interface/assert',
                    'lldp/show', 'ospf/show'],
    'ipAddress=10.0.0.11': ['arpnd/show'],
    'ipvers=v4': ['address/show'],
    'local=True': ['mac/show'],
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
    'result=pass': ['bgp/assert', 'evpnVni/assert', 'interfaces/assert',
                    'ospf/assert', 'sqpoller/show'],
    'result=fail': ['bgp/assert', 'evpnVni/assert', 'interfaces/assert',
                    'ospf/assert'],
    'result=all': ['bgp/assert', 'evpnVni/assert', 'interfaces/assert',
                   'ospf/assert'],
    'status=alive': ['device/show'],
    'status=dead': ['device/show'],
    'status=neverpoll': ['device/show'],
    'vlanName=vlan13': ['vlan/show'],
    'state=active': ['vlan/show'],
    'query_str=hostname%20==%20"leaf01"': ['all/show', 'all/summarize',
                                           'all/unique'],
    'via=arpnd': ['topology/show'],
    'via=lldp&via=arpnd': ['topology/show'],
    'macaddr=44:39:39:ff:00:13&macaddr=44:39:39:ff:00:24': ['mac/show'],
    'macaddr=4439.39ff.4095': ['mac/show'],
    'macaddr=4439.39FF.4095': ['mac/show'],
    'macaddr=44:39:39:FF:40:95': ['mac/show'],
    'macaddr=44:39:39:ff:40:95': ['mac/show'],
    'query_str=hostname=="leaf01"%20and%201000<mtu<2000':
    ['interface/show', 'interface/summaeize', 'interface/unique'],
    'what=mtu': ['interface/top'],
    'what=numChanges': ['bgp/top', 'ospf/top', 'interface/top'],
    'what=uptime': ['device/top'],
    'what=prefixLen': ['route/top'],
    'columns=vrf': ['address/unique', 'route/unique'],
    'pollExcdPeriodCount=!0': ['sqPoller/show'],
    'pollExcdPeriodCount=0': ['sqPoller/show'],
}

GOOD_FILTER_EMPTY_RESULT_FILTER = [
    'sqPoller/show?status=fail',
    'evpnVni/assert?result=fail',
    'device/show?status=neverpoll',
    'device/show?status=dead',
    'vlan/unique?state=notConnected',
    'sqPoller/show?pollExcdPeriodCount=!0',
    'arpnd/summarize?macaddr=44:39:39:FF:40:95',
    'mac/summarize?macaddr=44:39:39:FF:40:95',
    'arpnd/summarize?macaddr=4439.39FF.4095',
    'mac/summarize?macaddr=4439.39FF.4095',
    'arpnd/summarize?macaddr=4439.39ff.4095',
    'mac/summarize?macaddr=4439.39ff.4095',
    'sqPoller/summarize?status=fail',
    'device/summarize?status=dead',
    'device/summarize?status=neverpoll',
    'vlan/summarize?state=up',
    'vlan/summarize?state=down',
    'vlan/summarize?state=pass',
    'vlan/summarize?state=notConnected',
    'sqPoller/summarize?pollExcdPeriodCount=!0',
    'inventory/show?hostname=leaf01',
    'inventory/show?namespace=ospf-ibgp',
    'inventory/show?hostname=leaf01&hostname=spine01',
    'inventory/show?namespace=ospf-ibgp&namespace=ospf-single',
    'inventory/show?type=ethernet',
    'inventory/show?query_str=hostname%20==%20"leaf01"',
    'inventory/summarize?hostname=leaf01',
    'inventory/summarize?namespace=ospf-ibgp',
    'inventory/summarize?hostname=leaf01&hostname=spine01',
    'inventory/summarize?namespace=ospf-ibgp&namespace=ospf-single',
    'inventory/summarize?type=ethernet',
    'inventory/summarize?query_str=hostname%20==%20"leaf01"',
]

GOOD_SERVICE_VERBS = {
    'show': 'all',
    'unique': 'all',
    'summarize': 'all',
    'assert': ['bgp', 'interface', 'ospf'],
    'lpm': ['route'],
    'find': ['network'],
    'describe': ['tables']
}

MANDATORTY_VERB_ARGS = {
    # Use namespace as it is present in every object
    'unique': ['columns'],
    'lpm': ['address'],
    'find': ['address'],
    'top': ['what'],
}

MANDATORY_SERVICE_ARGS = {
    'path': ['src', 'dest', 'namespace'],
}

####
# Validation functions: Needed especially for filters that specify multiple
# values for a single key.
####


def _validate_hostname_output(json_out, service, verb, _):
    if verb == "summarize":
        pass
    if service in ['network']:
        # nework has no hostname column
        pass
    elif service in ["mac", "vlan", "mlag", "evpnVni"]:
        # MAC addr is not present on spines
        assert ({x['hostname'] for x in json_out} == set(['leaf01']))
    else:
        assert ({x['hostname'] for x in json_out}
                == set(['leaf01', 'spine01']))
    return True


def _validate_namespace_output(json_out, service, verb, _):
    if verb == "summarize":
        if service == "network":
            # network summarize has no namespace column
            return
        # summarize output has namespace as a key
        if service in ["bgp", "evpnVni", "devconfig", "mlag"]:
            assert(set(json_out.keys()) == set(['ospf-ibgp']))
        else:
            assert (set(json_out.keys()) == set(['ospf-ibgp', 'ospf-single']))
    else:
        if service in ["bgp", "evpnVni", "devconfig", "mlag"]:
            assert({x['namespace'] for x in json_out} == set(['ospf-ibgp']))
        else:
            assert ({x['namespace'] for x in json_out} == set(['ospf-ibgp',
                                                               'ospf-single']))


def _validate_route_protocol(json_out, _, _2, _3):
    assert ({x['protocol'] for x in json_out} == set(['ospf', 'bgp']))


def _validate_macaddr_output(json_out, _, _2, _3):
    assert ({x['macaddr'] for x in json_out}
            == set(['44:39:39:ff:00:13', '44:39:39:ff:00:24']))


def _validate_columns_output(json_out, _, _2, args):
    columns = args.split('=')[1]
    assert ({x[columns] for x in json_out} != set())


VALIDATE_OUTPUT_FILTER = {
    'namespace=ospf-ibgp&namespace=ospf-single': _validate_namespace_output,
    'hostname=leaf01&hostname=spine01': _validate_hostname_output,
    'protocol=bgp&protocol=ospf': _validate_route_protocol,
    'macaddr=44:39:39:ff:00:13&macaddr=44:39:39:ff:00:24':
    _validate_macaddr_output,
    'columns=namespace': _validate_columns_output,
    'columns=vrf': _validate_columns_output,
}

####
# Test functions start
####


@ dataclass
class RouteSpecs:
    verbs: List[str]
    query_params: List[str]


def get_app_routes(sq_app: FastAPI) -> Dict:
    def extract_verbs_from_model(model: ModelField) -> List[str]:
        verbs_enum = model.type_
        return [e.value for e in verbs_enum]

    def extract_query_params_from_models(models: List[ModelField]) \
            -> List[str]:
        return [m.name for m in models]

    def check_token(route: APIRoute):
        error_msg = f'Missing token in {route.path}'
        try:
            assert route.dependant.dependencies[0].name == 'token', error_msg
        except Exception:
            assert False, error_msg

    def check_func_name(route: APIRoute, table: str):
        """ Check the function is called <something>_<table>.
        If not, the read_shared function won't work correctly
        """
        fun_name = route.dependant.call.__name__
        assert fun_name.split('_')[1] == table, \
            (f'Wrong function name for {route.path}. It should be similar to '
             f'query_{table}'
             )

    app_routes = {}
    for route in sq_app.routes:
        path = route.path
        if not path.startswith('/api/v2/'):
            continue
        if path == '/api/v2/{command}':
            # reserved route for wrong params
            continue
        check_token(route)
        path = path.split('/api/v2/')[1]
        table, verbs = path.split('/')
        check_func_name(route, table)
        if verbs == '{verb}':
            verb_model = route.dependant.path_params[0]
            verbs = extract_verbs_from_model(verb_model)
        else:
            # the verb is explicitly written in the route
            verbs = [verbs]
        if table not in app_routes:
            app_routes[table] = []
        # append 'token' query_param
        query_params = extract_query_params_from_models(
            route.dependant.query_params)
        app_routes[table].append(RouteSpecs(verbs, query_params))

    return app_routes


def get_args_to_match(sqobj: SqObject, verbs: List[str]) -> List[str]:
    args = []
    if sqobj.table == 'tables':
        args += ['table']
    if 'find' in verbs:
        return sqobj._valid_find_args
    return args + (sqobj._valid_assert_args if sqobj._valid_assert_args
                   else sqobj._valid_get_args)


def get_supported_verbs(sqobj: SqObject) -> List[str]:
    if sqobj.table == 'routes':
        supported_verbs = [e.value for e in RouteVerbs]
    else:
        if sqobj._valid_assert_args:
            # the assertion is supported for this class
            supported_verbs = [e.value for e in CommonExtraVerbs]
        else:
            supported_verbs = [e.value for e in CommonVerbs]
        if sqobj.table == 'tables':
            supported_verbs.append('describe')

    if sqobj.table == 'network':
        supported_verbs += [e.value for e in NetworkVerbs]

    return supported_verbs


def assert_missing_args(exp: set, got: set, set_name: str, table: str):
    missing_args = list(exp.difference(got))
    assert False, f'Missing {set_name} arguments {missing_args} from {table}'


def get(endpoint, service, verb, args):
    '''Make the call'''
    api_key = get_configured_api_key()
    url = f"{endpoint}/{service}/{verb}?{args}"

    # Check if we need to add the mandatory filter for the keyword
    for mandatory_column in MANDATORTY_VERB_ARGS.get(verb, []):
        if mandatory_column not in args:
            return -1

    for mandatory_column in MANDATORY_SERVICE_ARGS.get(service, []):
        if mandatory_column not in args:
            return -1

    # Check if we need to add the mandatory filter for the keyword

    client = TestClient(app)
    response = client.get(url, headers={API_KEY_NAME: api_key})

    c_v = f"{service}/{verb}"
    c_v_f = f"{c_v}?{args}"
    c_all = f"{service}/all"

    verb_use = GOOD_SERVICE_VERBS.get(verb, [])
    if 'all' not in verb_use and service not in verb_use:
        return -1

    argval = GOOD_FILTERS_FOR_SERVICE_VERB.get(args, [])

    if response.status_code != 200:
        if c_v in argval or argval == ['all']:
            assert False, f"{c_v_f} should not be in good responses list"
    else:
        validate_output = False
        if c_v in argval or argval == ['all']:
            validate_output = True
            df = pd.DataFrame(json.loads(
                response.content.decode('utf-8')))
            if ((c_v_f not in GOOD_FILTER_EMPTY_RESULT_FILTER) and
                    (c_all not in GOOD_FILTER_EMPTY_RESULT_FILTER)):
                assert(not df.empty)
            else:
                assert df.empty
        else:
            for _ in argval:
                if f'{service}/{verb}' in GOOD_FILTERS_FOR_SERVICE_VERB:
                    validate_output = True
                    match_verb = argval[0].split('/')[1]
                    assert match_verb == verb, \
                        f"Unable to match good result for {c_v_f}"

        if ((c_v_f not in GOOD_FILTER_EMPTY_RESULT_FILTER) and
                (c_all not in GOOD_FILTER_EMPTY_RESULT_FILTER)):

            if args in VALIDATE_OUTPUT_FILTER and validate_output:
                VALIDATE_OUTPUT_FILTER[args](
                    response.json(), service, verb, args)
            else:
                df = pd.DataFrame(json.loads(response.content.decode('utf-8')))
                assert(not df.empty)
        else:
            df = pd.DataFrame(json.loads(response.content.decode('utf-8')))
            assert df.empty

    return response.status_code


@ pytest.mark.rest
@ pytest.mark.parametrize("service", [
    pytest.param(cmd, marks=getattr(pytest.mark, cmd))
    for cmd in cli_commands])
@ pytest.mark.parametrize("verb", [
    pytest.param(verb, marks=getattr(pytest.mark, verb))
    for verb in VERBS])
@ pytest.mark.parametrize("arg", FILTERS)
# pylint: disable=redefined-outer-name, unused-argument
def test_rest_services(app_initialize, service, verb, arg):
    '''Main workhorse'''
    get(ENDPOINT, service, verb, arg)


@ pytest.mark.rest
@ pytest.mark.parametrize("service, verb", [
    (cmd, verb) for cmd in TABLES for verb in VERBS])
def test_rest_arg_consistency(service, verb):
    '''check that the arguments used in REST match whats in sqobjects'''

    alias_args = {'path': {'source': 'src'}}

    if service == 'network' and verb not in [e.value for e in NetworkVerbs]:
        return

    if verb == "describe" and not service == "tables":
        return
    if service in ['topcpu', 'topmem', 'ospfIf', 'ospfNbr', 'time',
                   'ifCounters']:
        return
    # import all relevant functions from the rest code first

    fnlist = list(filter(lambda x: x[0] == f'query_{service}_{verb}',
                         inspect.getmembers(query, inspect.isfunction)))
    if not fnlist and service.endswith('s'):
        # Try the singular version
        fnlist = list(filter(lambda x: x[0] == f'query_{service[:-1]}_{verb}',
                             inspect.getmembers(query, inspect.isfunction)))

    if fnlist:
        found_service_rest_fn = True
    else:
        found_service_rest_fn = False
        fnlist = list(filter(lambda x: x[0] == f'query_{service}',
                             inspect.getmembers(query, inspect.isfunction)))
    if not fnlist and service.endswith('s'):
        # Try the singular version
        fnlist = list(filter(lambda x: x[0] == f'query_{service[:-1]}',
                             inspect.getmembers(query, inspect.isfunction)))
    if not fnlist:
        assert fnlist, f"No functions found for {service}/{verb}"

    for fn in fnlist:
        rest_args = []

        for i in inspect.getfullargspec(fn[1]).args:
            if i in ['verb', 'token', 'request']:
                continue
            aliases = alias_args.get(service, {})
            val = i if i not in aliases else aliases[i]
            rest_args.append(val)

        sqobj = get_sqobject(service)()
        supported_verbs = {x[0].replace('aver', 'assert')
                           .replace('get', 'show')
                           for x in inspect.getmembers(sqobj)
                           if inspect.ismethod(x[1]) and
                           not x[0].startswith('_')}

        if verb not in supported_verbs:
            continue

        aliases = alias_args.get(service, {})

        arglist = getattr(sqobj, f'_valid_{verb}_args', None)
        if not arglist:
            if verb == "show":
                arglist = getattr(sqobj, '_valid_get_args', None)
            else:
                warnings.warn(
                    f'Skipping arg check for {verb} in {service} due to '
                    f'missing valid_args list', category=ImportWarning)
                return

        arglist.extend(['namespace', 'hostname', 'start_time', 'end_time',
                        'format', 'view', 'columns', 'query_str'])

        valid_args = set(arglist)

        if service == 'device':
            valid_args.remove('ignore_neverpoll')

        # In the tests below, we warn when we don't have the exact
        # {service}_{verb} REST function, which prevents us from picking the
        # correct set of args.
        for arg in valid_args:
            assert arg in rest_args, \
                f"{arg} missing from {fn} arguments for verb {verb}"

        for arg in rest_args:
            if arg not in valid_args and arg != "result":
                # result is usually part of assert keyword and so ignore
                if found_service_rest_fn:
                    assert False, \
                        f"{arg} not in {service} sqobj {verb} arguments"
                else:
                    warnings.warn(
                        f"{arg} not in {service} sqobj {verb} arguments",
                        category=ImportWarning)


@ pytest.fixture()
def app_initialize():
    '''Initialize the test server'''

    # pylint: disable=import-outside-toplevel
    from suzieq.restServer.query import app_init

    cfgfile = create_dummy_config_file(
        datadir='./tests/data/parquet')
    app_init(cfgfile)
    yield
    os.remove(cfgfile)


# The basic test harness for fastapi doesn't really start a server
# so we need to test this separately. xdist tries to run tests in parallel
# which screws things up. So, we run server with & without https sequentially
# For some reason, putting the no_https in a for loop didn't work either
@ pytest.mark.rest
@ pytest.mark.filterwarnings(
    'ignore::urllib3.exceptions.InsecureRequestWarning')
def test_rest_server():
    '''Try starting the REST server, actually'''
    # pylint: disable=import-outside-toplevel
    import subprocess
    from time import sleep

    import requests

    cfgfile = create_dummy_config_file(
        datadir='./tests/data/parquet')

    # pylint: disable=consider-using-with
    server = subprocess.Popen(
        f'./suzieq/restServer/sq_rest_server.py -c {cfgfile} --no-https'
        .split())
    sleep(5)
    assert(server.pid)
    assert(requests.get('http://localhost:8000/api/docs'))
    server.kill()
    sleep(5)

    # pylint: disable=consider-using-with
    server = subprocess.Popen(
        f'./suzieq/restServer/sq_rest_server.py -c {cfgfile} '.split())
    sleep(5)
    assert(server.pid)
    assert(requests.get('https://localhost:8000/api/docs', verify=False))
    server.kill()
    sleep(5)

    os.remove(cfgfile)


@ pytest.mark.rest
def test_routes_sqobj_consistency():
    """Checks if the app routes params are consistent with the sqobject
       params"""
    routes = get_app_routes(app)
    config_file = create_dummy_config_file()
    common_args = {'namespace', 'hostname', 'start_time', 'end_time',
                   'format', 'view', 'columns', 'query_str'}
    top_args = {'what', 'reverse', 'count'}
    for table, table_routes in routes.items():
        table_verbs = []
        try:
            sqobj = get_sqobject(table)(config_file=config_file)
        except ModuleNotFoundError as e:
            assert False, e

        supported_verbs = get_supported_verbs(sqobj)
        unsupported_verbs = [v for v in supported_verbs
                             if not getattr(sqobj,  cleanup_verb(v), None)]
        if unsupported_verbs:
            # some of the verbs specified in the REST server aren't supported
            # by the sqobject
            assert False, f'{unsupported_verbs} verbs not supported by {table}'

        for route in table_routes:
            table_verbs += route.verbs
            check_top = ('top' in route.verbs)
            # for /api/v2/table/describe we do not have common_args
            check_common = (table != 'table' or route.verbs != ['describe'])
            query_params = set(route.query_params)

            if check_common and not common_args.issubset(query_params):
                assert_missing_args(common_args, query_params, 'mandatory',
                                    table)
            query_params = query_params.difference(common_args)

            if check_top and not top_args.issubset(query_params):
                assert_missing_args(top_args, query_params, 'top', table)
            query_params = query_params.difference(top_args)

            if table == 'network' and 'find' not in route.verbs:
                # do not check deprecated commands. They are already checked
                continue
            args_to_match = get_args_to_match(sqobj, route.verbs)
            args_to_match = {a for a in args_to_match
                             if a not in common_args.union(top_args)}
            if table == 'device':
                args_to_match.remove('ignore_neverpoll')
            if args_to_match != query_params:
                assert False, (f'different query params for {table}: expected '
                               f'{args_to_match}. Got {query_params}')

        if set(table_verbs) != set(supported_verbs):
            assert False, (f'different verbs for {table}: expected '
                           f'{table_verbs}. Got {supported_verbs}')
