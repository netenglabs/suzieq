from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Depends, Security
from fastapi.security.api_key import APIKeyQuery, APIKey
from starlette import status
import logging
import uuid
import uvicorn
import argparse
import sys
import yaml
import inspect

from suzieq.sqobjects import *
from suzieq.utils import validate_sq_config

API_KEY = '1234asdfag'
API_KEY_NAME = 'access_token'

api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)


app = FastAPI()


# TODO: logging to this file isn't working
logging.FileHandler('/tmp/rest-server.log')
logger = logging.getLogger(__name__)


async def get_api_key(api_key_query: str = Security(api_key_query)):
    if api_key_query == API_KEY:
        return api_key_query
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )


# for now we won't support top for REST API
#  this is because a lot of top logic is currently in commands
#  and I'm not sure what needs to get abstracted out
@app.get('/api/v1/{command}/top')
async def no_top(command: str):
    u = uuid.uuid1()
    msg = f"top not supported for {command}: id={u}"
    logger.warning(msg)
    raise HTTPException(status_code=404, detail=msg)


"""
each of these read functions behaves the same, it gets the arguments
puts them into dicts and passes them to sqobjects

assume that all API functions are named read_*
"""


@app.get("/api/v1/address/{verb}")
async def read_address(verb: str,
                       token: str = Depends(get_api_key),
                       hostname: str = None,
                       start_time: str = "", end_time: str = "",
                       view: str = "latest", namespace: str = None,
                       columns: str = None, address: str = None,
                       ipvers: str = None,
                       vrf: str = None,
                       ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/arpnd/{verb}")
async def read_arpnd(verb: str,
                     token: str = Depends(get_api_key),
                     hostname: str = None,
                     start_time: str = "", end_time: str = "",
                     view: str = "latest", namespace: str = None,
                     columns: str = None, ipAddress: str = None,
                     macaddr: str = None,
                     oif: str = None,
                     ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/bgp/{verb}")
async def read_bgp(verb: str,
                   token: str = Depends(get_api_key),
                   hostname: str = None,
                   start_time: str = "", end_time: str = "",
                   view: str = "latest", namespace: str = None,
                   columns: str = None, peer: str = None,
                   state: str = None, status: str = None,
                   vrf: str = None,
                   ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/device/{verb}")
async def read_device(verb: str,
                      token: str = Depends(get_api_key),
                      hostname: str = None,
                      start_time: str = "", end_time: str = "",
                      view: str = "latest", namespace: str = None,
                      columns: str = None,
                      ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/evpnVni/{verb}")
async def read_evpnVni(verb: str,
                       token: str = Depends(get_api_key),
                       hostname: str = None,
                       start_time: str = "", end_time: str = "",
                       view: str = "latest", namespace: str = None,
                       columns: str = None, vni: str = None,
                       ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/fs/{verb}")
async def read_fs(verb: str,
                  token: str = Depends(get_api_key),
                  hostname: str = None,
                  start_time: str = "", end_time: str = "",
                  view: str = "latest", namespace: str = None,
                  columns: str = None, mountPoint: str = None,
                  usedPercent: str = None,
                  ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/interface/{verb}")
async def read_interface(verb: str,
                         token: str = Depends(get_api_key),
                         hostname: str = None,
                         start_time: str = "", end_time: str = "",
                         view: str = "latest", namespace: str = None,
                         columns: str = None,
                         ifname: str = None, state: str = None,
                         type: str = None, what: str = None,
                         matchval: int = Query(None, alias="value"),
                         ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/lldp/{verb}")
async def read_lldp(verb: str,
                    token: str = Depends(get_api_key),
                    hostname: str = None,
                    start_time: str = "", end_time: str = "",
                    view: str = "latest", namespace: str = None,
                    columns: str = None, ifname: str = None,
                    ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/mlag/{verb}")
async def read_mlag(verb: str,
                    token: str = Depends(get_api_key),
                    hostname: str = None,
                    start_time: str = "", end_time: str = "",
                    view: str = "latest", namespace: str = None,
                    columns: str = None,
                    ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/ospf/{verb}")
async def read_ospf(verb: str,
                    token: str = Depends(get_api_key),
                    hostname: str = None,
                    start_time: str = "", end_time: str = "",
                    view: str = "latest", namespace: str = None,
                    columns: str = None,  ifname: str = None,
                    state: str = None,
                    vrf: str = None,
                    ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/mac/{verb}")
async def read_mac(verb: str,
                   token: str = Depends(get_api_key),
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


# path doesn't support unique at all
@app.get("/api/v1/path/unique")
async def no_path_unique():
    return return_error(404, 'Unique not supported for path')


@app.get("/api/v1/path/{verb}")
async def read_path(verb: str,
                    token: str = Depends(get_api_key),
                    hostname: str = None,
                    start_time: str = "", end_time: str = "",
                    view: str = "latest", namespace: str = None,
                    columns: str = None,
                    dest: str = None,
                    source: str = Query(None, alias="src")
                    ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/route/{verb}")
async def read_route(verb: str,
                     token: str = Depends(get_api_key),
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
async def read_sqpoller(verb: str,
                        token: str = Depends(get_api_key),
                        hostname: str = None,
                        start_time: str = "", end_time: str = "",
                        view: str = "latest", namespace: str = None,
                        columns: str = None, service: str = None,
                        add_filter: str = None
                        ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/topology/{verb}")
async def read_topology(verb: str,
                        token: str = Depends(get_api_key),
                        hostname: str = None,
                        start_time: str = "", end_time: str = "",
                        view: str = "latest", namespace: str = None,
                        columns: str = None, polled_neighbor: bool = None,
                        vrf: str = None,
                        ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/vlan/{verb}")
async def read_vlan(verb: str,
                    token: str = Depends(get_api_key),
                    hostname: str = None,
                    start_time: str = "", end_time: str = "",
                    view: str = "latest", namespace: str = None,
                    columns: str = None, vlan: str = None,
                    ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


@app.get("/api/v1/table/{verb}")
async def read_table(verb: str,
                     token: str = Depends(get_api_key),
                     hostname: str = None,
                     start_time: str = "", end_time: str = "",
                     view: str = "latest", namespace: str = None,
                     columns: str = None,
                     ):
    function_name = inspect.currentframe().f_code.co_name
    return read_shared(function_name, verb, locals())


def read_shared(function_name, verb, local_variables):
    """all the shared code for each of thse read functions"""

    command = function_name[5:]  # assumes the name of the function is read_*
    command_args, verb_args = create_filters(function_name, local_variables)

    verb = cleanup_verb(verb)

    ret, svc_inst = run_command_verb(command, verb, command_args, verb_args)
    check_args(function_name, svc_inst)
    return ret


def check_args(function_name, svc_inst):
    """make sure that all the args defined in sqobject are defined in the function"""

    arguments = inspect.getfullargspec(globals()[function_name]).args
    arguments = [i for i in arguments if i not in
                 ['verb', 'token', 'start_time', 'end_time', 'view']]

    valid_args = set(svc_inst._valid_get_args)
    if svc_inst._valid_assert_args:
        valid_args = valid_args.union(svc_inst._valid_assert_args)

    for arg in valid_args:
        assert arg in arguments, f"{arg} missing from {function_name} arguments"

    for arg in arguments:
        assert arg in valid_args, f"extra argument {arg} in {function_name}"


def create_filters(function_name, locals):
    command_args = {}
    verb_args = {}
    remove_args = ['verb', 'token']
    possible_args = ['hostname', 'namespace', 'start_time', 'end_time', 'view', 'columns']
    split_args = ['namespace', 'columns', 'address']
    both_verb_and_command = ['namespace', 'hostname', 'columns']

    arguments = inspect.getfullargspec(globals()[function_name]).args

    for arg in arguments:
        if arg in remove_args:
            continue
        if arg in possible_args:
            if locals[arg] is not None:
                command_args[arg] = locals[arg]
                if arg in split_args:
                    command_args[arg] = command_args[arg].split()
                if arg in both_verb_and_command:
                    verb_args[arg] = command_args[arg]
        else:
            if locals[arg] is not None:
                verb_args[arg] = locals[arg]
                if arg in split_args:
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


def run_command_verb(command, verb, command_args, verb_args):
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
        return_error(404, f"{verb} not supported for {command} or missing arguement: {err}")

    except NotImplementedError as err:
        return_error(404, f"{verb} not supported for {command}: {err}")

    except TypeError as err:
        return_error(405, f"bad keyword/filter for {command} {verb}: {err}")

    except ValueError as err:
        return_error(405, f"bad keyword/filter for {command} {verb}: {err}")

    except Exception as err:
        return_error(500, f"exceptional exception {verb} for {command} of type {type(err)}: {err}")

    if df.columns.to_list() == ['error']:
        return_error(405, f"bad keyword/filter for {command} {verb}: {df['error'][0]}")

    return df.to_json(orient="records"), svc_inst


def return_error(code: int, msg: str):
    u = uuid.uuid1()
    msg = f"{msg} id={u}"
    logger.warning(msg)
    raise HTTPException(status_code=code, detail=msg)


@app.get("/api/v1/{command}")
def missing_verb(command):
    return_error(404, f"{command} command missing a verb. for example '/api/v1/{command}/show'")


@app.get("/")
def bad_path():
    return_error(404, f"bad path. Try something like '/api/v1/device/show'")


def check_config_file(cfgfile):
    if cfgfile:
        with open(cfgfile, "r") as f:
            cfg = yaml.safe_load(f.read())

        validate_sq_config(cfg, sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str, help="alternate config file"
    )
    userargs = parser.parse_args()
    check_config_file(userargs.config)
    app.cfg_file = userargs.config

    uvicorn.run(app, host="0.0.0.0", port=8000,
                log_level='info', )
