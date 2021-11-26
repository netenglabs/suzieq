import uvicorn
from typing import Optional
from fastapi import FastAPI, Query, Request, HTTPException
from os.path import isfile, abspath, dirname, join
import json
import asyncio
from os import kill, getpid
import signal

FILE_NAME = "data.json"
SUZIEQ_PATH = dirname(abspath(__file__))
ERRORS_PATH = join(SUZIEQ_PATH, "errors")
VALID_TOKEN = "99499204e7a484d0825d962ae5225fb27f002963"

app = FastAPI()


def rest_main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    uvicorn.run(app, host="", port=9000)


def getData(path):
    # remove the first "/" in order to make os.path.join work correctly
    if path[0] == "/":
        path = path[1:]
    file_path = join(SUZIEQ_PATH, path, FILE_NAME)
    if not isfile(file_path):
        return None, getError("404.page_not_found")
    with open(file_path, "r") as f:
        return json.loads(f.read()), None


def getError(error):
    error_path = join(ERRORS_PATH, error)
    if not isfile(error_path):
        return 500, "Internal error"
    error_code = int(error.split(".")[0])
    with open(error_path, "r") as f:
        return error_code, f.read()


@app.get("/api/dcim/devices/")
async def getDevices(
    request: Request,
    tag: Optional[str] = Query(None, max_length=50),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(None),
):

    token = request.headers.get("authorization", None)
    if not token:
        error_code, error = getError("403.no_token")
        raise HTTPException(status_code=error_code, detail=error)
    token = token.split()[1]
    if token != VALID_TOKEN:
        error_code, error = getError("403.invalid_token")
        raise HTTPException(status_code=error_code, detail=error)

    result = getData("/api/dcim/devices/")
    if result[1] is not None:
        error_code, error = result[1]
        raise HTTPException(status_code=error_code, detail=error)
    in_devices = result[0].get("results", [])
    if tag == "null":
        tag = None
    devices = []
    for d in in_devices:
        if len(
            list(filter(lambda t: t["name"] == tag, d.get("tags", [])))
        ) > 0:
            devices.append(d)

    if not devices and tag is not None:
        return {
            "tag": [
                "Select a valid choice. {} is not one of the available "
                "choices.".format(tag)
            ]
        }

    if not limit:
        limit = 50

    if not offset:
        offset = 0

    res = {
        "count": len(devices),
        "previous": None,
        "next": None
    }

    if offset != 0:
        devices = devices[offset:]
        if offset - limit < 0:
            res["previous"] = "/api/dcim/devices/?limit={}&tag={}"\
                              .format(limit, tag)
        else:
            res["previous"] = "/api/dcim/devices/?limit={}&offset={}&tag={}"\
                              .format(limit, offset - limit, tag)

    if len(devices) > limit:
        devices = devices[:limit]
        res["next"] = "/api/dcim/devices/?limit={}&offset={}&tag={}".format(
            limit, offset + limit, tag
        )

    res["results"] = devices
    return res


@app.post("/api/users/tokens/provision/", status_code=201)
async def getToken(request: Request):
    valid_credentials = {"username": "admin", "password": "admin"}
    credentials = await request.json()
    if credentials != valid_credentials:
        error_code, error = getError("403.invalid_credentials")
        raise HTTPException(status_code=error_code, detail=error)

    result = getData("/api/users/tokens/provision/")
    if result[1] is not None:
        error_code, error = result[1]
        raise HTTPException(status_code=error_code, detail=error)

    return result[0]


@app.post("/kill")
async def server_kill():
    kill(getpid(), signal.SIGTERM)


if __name__ == "__main__":
    rest_main()
