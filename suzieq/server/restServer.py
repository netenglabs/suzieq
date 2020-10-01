from typing import Optional
from fastapi import FastAPI, HTTPException
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


@app.get("/api/v1/path/{verb}")
async def read_path(verb: str, namespace: str = "", start_time: str = "",
                    end_time: str = "", src: str = "", dest: str = "",
                    vrf: str = "", view: str = 'latest'):
    namespace = namespace.split()
    verb = cleanup_verb(verb)
    service_args = create_service_args('', start_time, end_time, view, namespace)

    verb_args = {'namespace': namespace,
                 'source': src,
                 'dest': dest,
                 'vrf': vrf}
    return run_service_verb('path', verb,  service_args, verb_args)


@app.get("/api/v1/route/lpm")
async def read_route_lpm(address: str = "",
                         hostname: str = "", start_time: str = "",
                         end_time: str = "", view: str = "latest",
                         namespace: str = "", ):
    service_args = create_service_args(hostname, start_time, end_time, view, namespace)

    verb_args = {'hostname': hostname,
                 'namespace': namespace,
                 'address': address}
    return run_service_verb('route', 'lpm',  service_args, verb_args)


@app.get("/api/v1/{service}/{verb}")
async def read_service(service: str, verb: str, hostname: str = "",
                       start_time: str = "", end_time: str = "",
                       view: str = "latest", namespace: str = ""):
    """
    Get data from **service** and **verb**

    - allows filters of **hostname**, **namespace**, **start_time**, **end_time**, and **view**
    """
    verb = cleanup_verb(verb)
    service_args = create_service_args(hostname, start_time, end_time, view, namespace)

    verb_args = {'hostname': hostname,
                 'namespace': namespace}
    if verb == 'summarize':
        verb_args.pop('hostname', None)

    return run_service_verb(service, verb, service_args, verb_args)


def cleanup_verb(verb):
    if verb == 'show':
        verb = 'get'
    if verb == 'assert':
        verb = 'aver'
    return verb


def create_service_args(hostname, start_time, end_time, view, namespace):
    service_args = {'hostname': hostname,
                    'start_time': start_time,
                    'end_time': end_time,
                    'view': view,
                    'namespace': namespace}
    return service_args


def get_svc(service):
    service_name = service

    # we almost have a consistent naming scheme, but not quite.
    # sometime there are s at the end and sometimes not
    try:
        module = globals()[service]
    except KeyError:
        service = f"{service}s"
        module = globals()[service]

    try:
        svc = getattr(module, f"{service.title()}Obj")
    except AttributeError:
        if service == 'interfaces':
            # interfaces doesn't follow the same pattern as everything else
            svc = getattr(module, 'IfObj')
        else:
            svc = getattr(module, f"{service_name.title()}Obj")
    return svc


def run_service_verb(service, verb, service_args, verb_args):
    svc = get_svc(service)
    try:
        return getattr(svc(**service_args, config_file=app.cfg_file), verb)(**verb_args).to_json(orient="records")

    except AttributeError as err:
        u = uuid.uuid1()
        msg = f"{verb} not supported for {service} or missing arguement: {err} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=404,
                            detail=msg)
    # TODO: why can't i catch NotImplemented? that's what I want here.
    except Exception as err:
        u = uuid.uuid1()
        msg = f"exceptional exception {verb} for {service}: {err} id={u}"
        logger.warning(msg)
        raise HTTPException(status_code=405,
                            detail=msg)


@app.get("/api/v1/{service}")
def missing_verb(service):
    u = uuid.uuid1()
    msg = f"{service} service missing a verb. for example '/api/v1/{service}/show' id={u}"
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
