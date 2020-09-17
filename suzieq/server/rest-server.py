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

@app.get("/api/v1/{service}/{verb}")
async def read_service(service: str, verb: str, hostname: str = "",
                      start_time: str = "", end_time: str = "",
                      view: str = "latest", namespace: str = ""):
    if verb == 'show':
        verb = 'get'
    service_name = service
    try: 
        module = globals()[service]
    except KeyError:
        service = f"{service}s"
        module = globals()[service]

    svc = getattr(module, f"{service.title()}Obj")

    service_args = {'hostname': hostname,
                    'start_time': start_time,
                    'end_time': end_time,
                    'view': view,
                    'namespace': 'namespace'}
    verb_args = {'hostname': hostname,
                'namespace': namespace}
    if verb == 'summarize':
        verb_args.pop('hostname', None)
    try:

        return getattr(svc(**service_args), verb)\
                            (**verb_args).to_json(orient="records")
    
    except AttributeError as err:
        u = uuid.uuid1()
        logger.warning(f"{verb} not supported for {service_name}: {err} id={u}")
        raise HTTPException(status_code=404, 
                            detail=f"{verb} not supported for {service_name}: {err} id={u}")
    # TODO: why can't i catch NotImplemented? that's what I want here?  
    except Exception as err:
        u = uuid.uuid1()
        logger.warning(f"exceptional exception {verb} for {service_name}: {err} id={u}")
        raise HTTPException(status_code=404, 
                            detail=f"exceptional exception {verb} for {service_name}: {err} id={u}")

@app.get("/api/v1/{service}")
def missing_verb(service):
    u = uuid.uuid1()
    logger.warning(f"{service} service missing a verb id={u}")
    raise HTTPException(status_code=404,
                        detail=f"{service} service missing a verb. for example '/api/v1/service/show' id={u}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)