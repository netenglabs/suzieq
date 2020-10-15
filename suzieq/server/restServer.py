from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Request
import logging
import uuid
import uvicorn
import argparse
import sys
import yaml

from suzieq.sqobjects import *
from suzieq.utils import validate_sq_config

app = FastAPI()

# TODO: logging to this file isn't working
logging.FileHandler('/tmp/rest-server.log')
logger = logging.getLogger(__name__)


# for now we won't support top for REST API
#  this is because a lot of top logic is currently in commands
#  and I'm not sure what needs to get abstracted out
@app.get('/api/v1/{command}/top')
async def no_top(command: str):
    u = uuid.uuid1()
    msg = f"top not supported for {command}: id={u}"
    logger.warning(msg)
    raise HTTPException(status_code=404, detail=msg)


@app.get("/api/v1/device/{verb}", status_code=200)
async def read_command_device(verb: str, request: Request,
                                hostname: str = None, 
                                start_time: str = "", end_time: str = "",
                                view: str = "latest", namespace: str = "",
                                columns: str = None,
                                ):
    command = 'device'
    verb = cleanup_verb(verb)
    command_args, verb_args = get_filters(request.query_params)

    res =  run_command_verb(command, verb, command_args, verb_args)
    find_missing_args(verb_args, ['hostname', 'start_time', 'end_time',
                                        'view', 'namespace', 'columns'])
    return res

def get_filters(query_params):
    """ Rather than use the function arguments for query filters, we directly
    use the paramers that are sent in the request. This is because otherwise
    fastapi drops queries not specified as arguments, and we want to return 
    errors in that case
    """
    command_args = {}
    extra_args = {}
    possible_args = ['hostname', 'namespace', 'start_time', 'end_time', 'view', 'columns']
    split_args = ['namespace', 'columns']
    both_verb_and_command = ['namespace', 'hostname', 'columns']
    for param in query_params:
        if param in possible_args:
            if query_params[param] is not None:
                command_args[param] = query_params[param]
                if param in split_args:
                    command_args[param] = command_args[param].split()
                if param in both_verb_and_command:
                    extra_args[param] = command_args[param]
        else:
            extra_args[param] = query_params[param]
    return command_args, extra_args


def find_missing_args(verb_args: dict, args: str):
    """compares args defined in function with params to make sure we have defined
    the right arguments
    The point is to help figure out if the arguments are correct, since we are only
    using them for documentation

    args needs to be the list of arguments from the function from the query filter
    """
    for vb in verb_args:
        if vb not in args:
            return_error(555, f"missing query arg {vb} BAD CODE!")




@app.get("/api/v1/{command}/{verb}")
async def read_command(command: str, verb: str, request: Request,
                       hostname: str = None,
                       start_time: str = "", end_time: str = "",
                       view: str = "latest", namespace: str = "",
                       address: str = None,
                       columns: str = None, vrf: str = None,
                       source: str = Query(None, alias="src"),
                       dest: str = None,
                       what: str = None, state: str = None, ifname: str = None,
                       ipAddress: str = None, oif: str = None, macaddr: str = None,
                       peer: str = None, protocol: str = None,
                       prefix: str = None, ipvers: str = None, status: str = None,
                       vni: str = None, mountPoint: str = None, 
                       interface_type: str = Query(None, alias="type"),
                       vlan: str = None, remoteVtepIp: str = None, bd: str = None,
                       localOnly: bool = None, prefixlen: str = None, service: str = None,
                       polled_neighbor: bool = None, 
                       ):
    """
    Get data from **command** and **verb**

    - followed by filters, in which there are many
    """
    verb = cleanup_verb(verb)
    command_args = create_command_args(hostname, start_time, end_time, view, 
                                       namespace, columns)

    if columns:
        columns=columns.split()
    verb_args = create_verb_args(namespace=namespace.split(), 
                                 columns=columns,
                                 vrf=vrf, hostname=hostname,
                                 source=source, dest=dest, what=what,
                                 state=state, ifname=ifname, 
                                 address=address,
                                 ipAddress=ipAddress, oif=oif,
                                 macaddr=macaddr, peer=peer,
                                 protocol=protocol, ipvers=ipvers,
                                 status=status, vni=vni, mountPoint=mountPoint,
                                 type=interface_type, vlan=vlan, remoteVtepIp=remoteVtepIp,
                                 bd=bd, localOnly=localOnly, prefixlen=prefixlen,
                                 service=service, polled_neighbor=polled_neighbor,
                                 prefix=prefix,
                                )

    return run_command_verb(command, verb, command_args, verb_args)


def create_verb_args(**kwargs):
    verb_args = {}
    for a in kwargs:
        if kwargs[a] is not None:
            verb_args[a] = kwargs[a]
    return verb_args


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
    command_name = command

    # we almost have a consistent naming scheme, but not quite.
    # sometime there are s at the end and sometimes not
    try:
        module = globals()[command]
    except KeyError:
        command = f"{command}s"
        module = globals()[command]

    try:
        svc = getattr(module, f"{command.title()}Obj")
    except AttributeError:
        if command == 'interfaces':
            # interfaces doesn't follow the same pattern as everything else
            svc = getattr(module, 'IfObj')
        else:
            svc = getattr(module, f"{command_name.title()}Obj")
    return svc


def run_command_verb(command, verb, command_args, verb_args):
    """ 
    Runs the command and verb with the command_args and verb_args as dictionaries

    HTTP Return Codes
        404 -- Missing command or argument (including missing valid path)
        405 -- Missing or incorrect query parameters
        422 -- 
        500 -- Exceptions
    """
    svc = get_svc(command)
    try:
        df = getattr(svc(**command_args, config_file=app.cfg_file), verb)(**verb_args)

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

    return df.to_json(orient="records")

def return_error(code: int, msg: str):
    u = uuid.uuid1()
    msg = f"{msg} id={u}"
    logger.warning(msg)
    raise HTTPException(status_code=code, detail=msg)


@app.get("/api/v1/{command}")
def missing_verb(command):
    u = uuid.uuid1()
    msg = f"{command} command missing a verb. for example '/api/v1/{command}/show' id={u}"
    logger.warning(msg)
    raise HTTPException(status_code=404, detail=msg)


@app.get("/")
def bad_path():
    u = uuid.uuid1()
    msg = f"bad path. you want to use something like '/api/v1/device/show' id={u}"
    logger.warning(msg)
    raise HTTPException(status_code=404, detail=msg)


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
