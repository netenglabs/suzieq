from typing import Optional
from fastapi import FastAPI, HTTPException, Query
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

#@app.get("/api/v1/topology/{verb}")
async def read_command_topology(verb: str, hostname: str = None, 
                                start_time: str = "", end_time: str = "",
                                view: str = "latest", namespace: str = "",
                                columns: str = 'default',
                                polled_neighbor: bool = False):
    command = 'topology'
    verb = cleanup_verb(verb)
    command_args = create_command_args(hostname, start_time, end_time, view, 
                                       namespace, columns)
    verb_args = create_verb_args(namespace=namespace.split(), columns=columns.split(), 
                                 polled_neighbor=polled_neighbor,
                                )
    return run_command_verb(command, verb, command_args, verb_args)

@app.get("/api/v1/{command}/{verb}")
async def read_command(command: str, verb: str, hostname: str = None,
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
                       vni: str = None, mountPoint: str = None, type: str = None,
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
    namespace = namespace.split()
    verb_args = {'namespace': namespace}



    if columns:
        columns = columns.split()
        verb_args['columns'] = columns
    if address is not None:
        verb_args['address'] = address
    if vrf is not None:
        verb_args['vrf'] = vrf
    if hostname is not None:
        verb_args['hostname'] = hostname
    if source is not None:
        verb_args['source'] = source
    if dest is not None:
        verb_args['dest'] = dest
    if vrf is not None:
        verb_args['vrf'] = vrf
    if what is not None:
        verb_args['what'] = what
    if state is not None:
        verb_args['state'] = state
    if ifname is not None:
        verb_args['ifname'] = ifname
    if ipAddress is not None:
        verb_args['ipAddress'] = ipAddress
    if oif is not None:
        verb_args['oif'] = oif
    if macaddr is not None:
        verb_args['macaddr'] = macaddr
    if peer is not None:
        verb_args['peer'] = peer
    if protocol is not None:
        verb_args['protocol'] = protocol
    if prefix is not None:
        verb_args['prefix'] = prefix
    if ipvers is not None:
        verb_args['ipvers'] = ipvers
    if status is not None:
        verb_args['status'] = status
    if vni is not None:
        verb_args['vni'] = vni
    if mountPoint is not None:
        verb_args['mountPoint'] = mountPoint
    if type is not None:
        verb_args['type'] = type
    if vlan is not None:
        verb_args['vlan'] = vlan
    if remoteVtepIp is not None:
        verb_args['remoteVtepIp'] = remoteVtepIp
    if bd is not None:
        verb_args['bd'] = bd
    if localOnly is not None:
        verb_args['localOnly'] = localOnly
    if prefixlen is not None:
        verb_args['prefixlen'] = prefixlen
    if service is not None:
        verb_args['service'] = service
    if polled_neighbor is not None:
        verb_args['polled_neighbor'] = polled_neighbor

    return run_command_verb(command, verb, command_args, verb_args)

def create_verb_args(**kwargs):
    verb_args = {}
    for a in kwargs:
        if kwargs[a]is not None:
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
    svc = get_svc(command)
    try:
        df = getattr(svc(**command_args, config_file=app.cfg_file), verb)(**verb_args)

    except AttributeError as err:
        u = uuid.uuid1()
        msg = f"{verb} not supported for {command} or missing arguement: {err} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=404,
                            detail=msg)

    except NotImplementedError as err:
        u = uuid.uuid1()
        msg = f"{verb} not supported for {command}: {err} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=404, detail=msg)

    except TypeError as err:
        u = uuid.uuid1()
        msg = f"bad keyword/filter for {command} {verb}: {err} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=405, detail=msg)

    except ValueError as err:
        u = uuid.uuid1()
        msg = f"bad keyword/filter for {command} {verb}: {err} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=405, detail=msg)

    except Exception as err:
        u = uuid.uuid1()
        msg = f"exceptional exception {verb} for {command} of type {type(err)}: {err} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=406,
                            detail=msg)

    if df.columns.to_list() == ['error']:
        u = uuid.uuid1()
        msg = f"bad keyword/filter for {command} {verb}: {df['error'][0]} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=405, detail=msg)

    return df.to_json(orient="records")


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

    uvicorn.run(app, host="0.0.0.0", port=8000)
