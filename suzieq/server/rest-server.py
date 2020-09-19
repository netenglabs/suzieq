from typing import Optional
from fastapi import FastAPI, HTTPException
import logging 
import uuid
import uvicorn

from suzieq.sqobjects import *


app = FastAPI()
# TODO: logging to this file isn't working
logging.FileHandler('/tmp/rest-server.log')
logger = logging.getLogger(__name__)



#@app.get("/api/v1/route/lpm")
#async def read_route_lpm():


@app.get("/api/v1/{service}/{verb}")
async def read_service(service: str, verb: str, hostname: str = "",
                      start_time: str = "", end_time: str = "",
                      view: str = "latest", namespace: str = ""):
    if verb == 'show':
        verb = 'get'
    if verb == 'assert':
        verb = 'aver'


    service_args = {'hostname': hostname,
                    'start_time': start_time,
                    'end_time': end_time,
                    'view': view,
                    'namespace': 'namespace'}
    verb_args = {'hostname': hostname,
                'namespace': namespace}
    if verb == 'summarize':
        verb_args.pop('hostname', None)
    
    svc = get_svc(service)

    return run_service_verb(svc, verb, service, service_args, verb_args)

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

def run_service_verb(svc, verb, name, service_args, verb_args):
    try:

        return getattr(svc(**service_args), verb)\
                            (**verb_args).to_json(orient="records")
    
    except AttributeError as err:
        u = uuid.uuid1()
        logger.warning(f"{verb} not supported for {name}: {err} id={u}")
        raise HTTPException(status_code=404, 
                            detail=f"{verb} not supported for {name}: {err} id={u}")
    # TODO: why can't i catch NotImplemented? that's what I want here. 
    except Exception as err:
        u = uuid.uuid1()
        logger.warning(f"exceptional exception {verb} for {name}: {err} id={u}")
        raise HTTPException(status_code=404, 
                            detail=f"exceptional exception {verb} for {name}: {err} id={u}")

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)