import uvicorn
from typing import Optional
from fastapi import FastAPI, Query
from os.path import isfile, abspath
import json

FILE_NAME = "data.json"
SUZIEQ_PATH = abspath("./suzieq/inventoryProvider/tests/")
ERRORS_PATH = SUZIEQ_PATH + "errors/"

app = FastAPI()

def rest_main():
    uvicorn.run(app, host='', port=9000)

def getData(path):
    file_path = SUZIEQ_PATH + path + FILE_NAME
    if not isfile(file_path):
        return None, getError("page_not_found")
    with open(file_path, "r") as f:
        return json.loads(f.read()), None

def getError(error):
    error_path = ERRORS_PATH + error
    if not isfile(error_path):
        print(error_path)
        raise ValueError("Unknown error {}".format(error))
    with open(error_path, "r") as f:
        return f.read()

@app.get("/api/dcim/devices/")
async def getDevices(
    tag: Optional[str] = Query(None, max_length=50),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(None)
):
    result, error = getData("/api/dcim/devices/")
    if error:
        return error
    in_devices = result.get("results", [])
    devices = []
    for d in in_devices:
        if len(list(filter(lambda t: t["name"] == tag, d.get("tags", [])))) > 0:
            devices.append(d)

    if not devices:
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
        res["next"] = "/api/dcim/devices/?limit={}&offset={}&tag={}"\
                      .format(limit, offset + limit, tag)

    res["results"] = devices
    return res

@app.post("/api/users/tokens/provision/")
async def getToken():
    return {"token":"token-value"}

if __name__ == "__main__":
    rest_main()