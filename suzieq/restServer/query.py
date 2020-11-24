from typing import Optional
import json
from enum import Enum
from fastapi import FastAPI, HTTPException, Query, Depends, Security
from fastapi.security.api_key import APIKeyQuery, APIKeyHeader
from fastapi.responses import Response
from starlette import status
import uuid
import inspect
import logging
import uvicorn

from suzieq.sqobjects import *
from suzieq.utils import load_sq_config

API_KEY_NAME = 'access_token'

api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


app = FastAPI()


def get_configured_log_level():
    cfg = load_sq_config(config_file=app.cfg_file)
    log_level = cfg.get('logging-level', 'INFO').lower()
    return log_level


def get_log_file():
    cfg = load_sq_config(config_file=app.cfg_file)
    tmp = cfg.get('temp-directory', '/tmp')
    return f"{tmp}/sq-rest-server.log"


def get_configured_api_key():
    cfg = load_sq_config(config_file=app.cfg_file)
    try:
        api_key = cfg['API_KEY']
    except KeyError:
        print('missing API_KEY in config file')
        exit(1)

    return api_key


async def get_api_key(api_key_query: str = Security(api_key_query),
                      api_key_header: str = Security(api_key_header)):

    api_key = get_configured_api_key()
    if api_key_query == api_key:
        return api_key_query
    elif api_key_header == api_key:
        return api_key_header
    else:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )


"""
each of these read functions behaves the same, it gets the arguments
puts them into dicts and passes them to sqobjects

assume that all API functions are named read_*
"""


class CommonVerbs(str, Enum):
    show = "show"
    summarize = "summarize"
    unique = "unique"


class MoreVerbs(str, Enum):
    show = "show"
    summarize = "summarize"
    unique = "unique"
    aver = "assert"


class RouteVerbs(str, Enum):
    show = "show"
    summarize = "summarize"
    unique = "unique"
    lpm = "lpm"


class PathVerbs(str, Enum):
    show = "show"
    summarize = "summarize"


class TableVerbs(str, Enum):
    show = "show"
    summarize = "summarize"
    describe = "describe"


@app.get("/api/v1/address/{verb}")
async def query_address(verb: CommonVerbs,
                        token: str = Depends(get_api_key),
                        format: str = None,
                        hostname: str = None,
                        start_time: str = "", end_time: str = "",
                        view: str = "latest", namespace: str = None,
                        columns: str = None, address: str = None,
                        ipvers: str = None,
                        vrf: str = None
                        ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/arpnd/{verb}")
async def query_arpnd(verb: CommonVerbs,
                      token: str = Depends(get_api_key),
                      format: str = None,
                      hostname: str = None,
                      start_time: str = "", end_time: str = "",
                      view: str = "latest", namespace: str = None,
                      columns: str = None, ipAddress: str = None,
                      macaddr: str = None,
                      oif: str = None
                      ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/bgp/{verb}")
async def query_bgp(verb: MoreVerbs,
                    token: str = Depends(get_api_key),
                    format: str = None,
                    hostname: str = None,
                    start_time: str = "", end_time: str = "",
                    view: str = "latest", namespace: str = None,
                    columns: str = None, peer: str = None,
                    state: str = None, vrf: str = None,
                    status: str = None,
                    ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/device/{verb}")
async def query_device(verb: CommonVerbs,
                       token: str = Depends(get_api_key),
                       format: str = None,
                       hostname: str = None,
                       start_time: str = "", end_time: str = "",
                       view: str = "latest", namespace: str = None,
                       columns: str = None
                       ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/evpnVni/{verb}")
async def query_evpnVni(verb: MoreVerbs,
                        token: str = Depends(get_api_key),
                        format: str = None,
                        hostname: str = None,
                        start_time: str = "", end_time: str = "",
                        view: str = "latest", namespace: str = None,
                        columns: str = None, vni: str = None,
                        status: str = None,
                        ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/fs/{verb}")
async def query_fs(verb: CommonVerbs,
                   token: str = Depends(get_api_key),
                   format: str = None,
                   hostname: str = None,
                   start_time: str = "", end_time: str = "",
                   view: str = "latest", namespace: str = None,
                   columns: str = None, mountPoint: str = None,
                   usedPercent: str = None
                   ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/interface/{verb}")
async def query_interface(verb: MoreVerbs,
                          token: str = Depends(get_api_key),
                          format: str = None,
                          hostname: str = None,
                          start_time: str = "", end_time: str = "",
                          view: str = "latest", namespace: str = None,
                          columns: str = None,
                          ifname: str = None, state: str = None,
                          type: str = None, what: str = None,
                          mtu: str = None,
                          matchval: int = Query(None, alias="value"),
                          status: str = None,
                          ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/lldp/{verb}")
async def query_lldp(verb: CommonVerbs,
                     token: str = Depends(get_api_key),
                     format: str = None,
                     hostname: str = None,
                     start_time: str = "", end_time: str = "",
                     view: str = "latest", namespace: str = None,
                     columns: str = None, ifname: str = None,
                     ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/mlag/{verb}")
async def query_mlag(verb: CommonVerbs,
                     token: str = Depends(get_api_key),
                     format: str = None,
                     hostname: str = None,
                     start_time: str = "", end_time: str = "",
                     view: str = "latest", namespace: str = None,
                     columns: str = None,
                     ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/ospf/{verb}")
async def query_ospf(verb: MoreVerbs,
                     token: str = Depends(get_api_key),
                     format: str = None,
                     hostname: str = None,
                     start_time: str = "", end_time: str = "",
                     view: str = "latest", namespace: str = None,
                     columns: str = None,  ifname: str = None,
                     state: str = None,
                     vrf: str = None,
                     status: str = None,
                     ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/mac/{verb}")
async def query_mac(verb: CommonVerbs,
                    token: str = Depends(get_api_key),
                    format: str = None,
                    hostname: str = None,
                    start_time: str = "", end_time: str = "",
                    view: str = "latest", namespace: str = None,
                    columns: str = None, bd: str = None,
                    localOnly: str = None,
                    macaddr: str = None, remoteVtepIp: str = None,
                    vlan: str = None,
                    ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/path/{verb}")
async def query_path(verb: PathVerbs,
                     token: str = Depends(get_api_key),
                     format: str = None,
                     hostname: str = None,
                     start_time: str = "", end_time: str = "",
                     view: str = "latest", namespace: str = None,
                     columns: str = None, vrf: str = None,
                     dest: str = None,
                     source: str = Query(None, alias="src")
                     ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/route/{verb}")
async def query_route(verb: RouteVerbs,
                      token: str = Depends(get_api_key),
                      format: str = None,
                      hostname: str = None,
                      start_time: str = "", end_time: str = "",
                      view: str = "latest", namespace: str = None,
                      columns: str = None, prefix: str = None,
                      vrf: str = None, protocol: str = None,
                      prefixlen: str = None, ipvers: str = None,
                      add_filter: str = None, address: str = None,
                      ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/sqpoller/{verb}")
async def query_sqpoller(verb: CommonVerbs,
                         token: str = Depends(get_api_key),
                         format: str = None,
                         hostname: str = None,
                         start_time: str = "", end_time: str = "",
                         view: str = "latest", namespace: str = None,
                         columns: str = None, service: str = None,
                         status: str = None,
                         ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/topology/{verb}")
async def query_topology(verb: PathVerbs,
                         token: str = Depends(get_api_key),
                         format: str = None,
                         hostname: str = None,
                         start_time: str = "", end_time: str = "",
                         view: str = "latest", namespace: str = None,
                         columns: str = None, polled_neighbor: str = None,
                         ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/vlan/{verb}")
async def query_vlan(verb: CommonVerbs,
                     token: str = Depends(get_api_key),
                     format: str = None,
                     hostname: str = None,
                     start_time: str = "", end_time: str = "",
                     view: str = "latest", namespace: str = None,
                     columns: str = None, vlan: str = None,
                     state: str = None,
                     ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/table/{verb}")
async def query_table(verb: TableVerbs,
                      token: str = Depends(get_api_key),
                      format: str = None,
                      hostname: str = None,
                      start_time: str = "", end_time: str = "",
                      view: str = "latest", namespace: str = None,
                      columns: str = None,
                      ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


def read_shared(function_name, verb, local_variables=None):
    """all the shared code for each of thse read functions"""

    command = function_name.split('_')[1]  # assumes fn name is query_<command>
    command_args, verb_args = create_filters(function_name, command,
                                             local_variables)

    verb = cleanup_verb(verb)

    columns = local_variables.get('columns', None)
    format = local_variables.get('format', None)
    ret, svc_inst = run_command_verb(
        command, verb, command_args, verb_args, columns, format)
    check_args(function_name, svc_inst)

    return ret


def check_args(function_name, svc_inst):
    """make sure that all the args defined in sqobject are defined in the function"""

    arguments = inspect.getfullargspec(globals()[function_name]).args
    arguments = [i for i in arguments if i not in
                 ['verb', 'token', 'format', 'start_time', 'end_time', 'view']]

    valid_args = set(svc_inst._valid_get_args)
    if svc_inst._valid_assert_args:
        valid_args = valid_args.union(svc_inst._valid_assert_args)

    for arg in valid_args:
        assert arg in arguments, f"{arg} missing from {function_name} arguments"

    for arg in arguments:
        assert arg in valid_args, f"extra argument {arg} in {function_name}"


def create_filters(function_name, command, locals):
    command_args = {}
    verb_args = {}
    remove_args = ['verb', 'token', 'format']
    possible_args = ['hostname', 'namespace',
                     'start_time', 'end_time', 'view', 'columns']
    split_args = {'all': ['namespace', 'hostname', 'columns', 'ifname', 'vlan', 'macaddr'],
                  'address': ['address'],
                  'arpnd': ['address', 'oif', ],
                  'bgp': ['vrf', 'peer'],
                  'evpnVni': ['vni'],
                  'fs': ['mountPoint'],
                  'interface': ['type'],
                  'mac': ['remoteVtepIp'],
                  'ospf': ['vrf'],
                  'route': ['prefix', 'protocol'],
                  }
    both_verb_and_command = ['namespace', 'hostname', ]

    arguments = inspect.getfullargspec(globals()[function_name]).args

    for arg in arguments:
        if arg in remove_args:
            continue
        if arg in possible_args:
            if locals[arg] is not None:
                command_args[arg] = locals[arg]
                if arg in split_args['all'] or arg in split_args.get(command,
                                                                     []):
                    command_args[arg] = command_args[arg].split()
                if arg in both_verb_and_command:
                    verb_args[arg] = command_args[arg]
        else:
            if locals[arg] is not None:
                verb_args[arg] = locals[arg]
                if arg in split_args['all'] or arg in split_args.get(command,
                                                                     []):
                    verb_args[arg] = verb_args[arg].split()

    return command_args, verb_args


def cleanup_verb(verb):
    if verb == 'show':
        verb = 'get'
    if verb == 'assert':
        verb = 'aver'
    return verb


def create_command_args(hostname='', start_time='', end_time='', view='latest',
                        namespace='', columns='default'):
    command_args = {'hostname': hostname,
                    'start_time': start_time,
                    'end_time': end_time,
                    'view': view,
                    'namespace': namespace,
                    'columns': columns}
    return command_args


def get_svc(command):
    """based on the command, find the module and service that the command is in
    return the service
    """
    command_name = command

    # we almost have a consistent naming scheme, but not quite.
    # sometime there are s at the end and sometimes not
    try:
        module = globals()[command]
    except KeyError:
        if command == 'sqpoller':
            command = 'sqPoller'
        else:
            command = f"{command}s"
        module = globals()[command]

    try:
        svc = getattr(module, f"{command.title()}Obj")
    except AttributeError:
        if command == 'interfaces':
            # interfaces doesn't follow the same pattern as everything else
            svc = getattr(module, 'IfObj')
        elif command == 'sqPoller':
            svc = getattr(module, 'SqPollerObj')
        else:
            svc = getattr(module, f"{command_name.title()}Obj")
    return svc


def run_command_verb(command, verb, command_args, verb_args, columns=['default'], format=None):
    """
    Runs the command and verb with the command_args and verb_args as dictionaries

    HTTP Return Codes
        404 -- Missing command or argument (including missing valid path)
        405 -- Missing or incorrect query parameters
        422 -- FastAPI validation errors
        500 -- Exceptions
    """
    svc = get_svc(command)
    try:
        svc_inst = svc(**command_args, config_file=app.cfg_file)
        df = getattr(svc_inst, verb)(**verb_args)

    except AttributeError as err:
        return_error(
            404, f"{verb} not supported for {command} or missing arguement: {err}")

    except NotImplementedError as err:
        return_error(404, f"{verb} not supported for {command}: {err}")

    except TypeError as err:
        return_error(405, f"bad keyword/filter for {command} {verb}: {err}")

    except ValueError as err:
        return_error(405, f"bad keyword/filter for {command} {verb}: {err}")

    except Exception as err:
        return_error(
            500, f"exceptional exception {verb} for {command} of type {type(err)}: {err}")

    if df.columns.to_list() == ['error']:
        return_error(
            405, f"bad keyword/filter for {command} {verb}: {df['error'][0]}")

    if columns != ['default'] and columns != ['*'] and columns is not None:
        df = df[columns]

    if format == 'markdown':
        # have to return a Reponse so that it won't turn the markdown into JSON
        return Response(content=df.to_markdown()), svc_inst

    if verb == 'summarize':
        json_orient = 'columns'
    else:
        json_orient = 'records'
    return json.loads(df.to_json(orient=json_orient)), svc_inst


def return_error(code: int, msg: str):
    u = uuid.uuid1()
    msg = f"{msg} id={u}"
    logger = logging.getLogger('uvicorn')
    logger.info(msg)
    raise HTTPException(status_code=code, detail=msg)


@app.get("/api/v1/{command}", include_in_schema=False)
def missing_verb(command):
    return_error(
        404, f'{command} command missing a verb. for example '
        f'/api/v1/{command}/show')


@app.get("/", include_in_schema=False)
def bad_path():
    return_error(404, "bad path. Try something like '/api/v1/device/show'")
