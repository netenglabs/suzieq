import uvicorn
from typing import Optional
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.routing import APIRoute
from os.path import isfile, abspath, dirname, join
import json
import yaml
import asyncio
from os import kill, getpid
import signal
import argparse
from random import randint

_SUZIEQ_PATH = dirname(abspath(__file__))
_ERRORS_PATH = join(_SUZIEQ_PATH, "errors")


class NetboxRestApp:
    def __init__(self, config_data) -> None:
        self.ip_addr = config_data.get("ip", "")
        self.port = config_data.get("port", 9000)
        self.netbox_name = config_data.get("netbox_name", "")
        if not self.netbox_name:
            raise ValueError("The field <netbox_name> must be set")
        self._file_name = self.netbox_name + ".json"

        result = self.getData("/api/users/tokens/provision/")
        if result[1]:
            raise RuntimeError("Problems retrieving valid tokens in init")

        # store list of valid tokens
        self._valid_tokens = {
            t["key"] for t in result[0] if t.get("key", None)
        }

        self.app = FastAPI(
            routes=[
                APIRoute(
                    "/api/dcim/devices/",
                    self.getDevices,
                    status_code=200,
                    methods=["GET"]
                ),
                APIRoute(
                    "/api/users/tokens/provision/",
                    self.getToken,
                    status_code=201,
                    methods=["POST"]
                ),
                APIRoute(
                    "/kill",
                    self.server_kill,
                    status_code=200,
                    methods=["POST"]
                )
            ]
        )

    def getData(self, path):
        # remove the first "/" to make os.path.join work properly
        if path[0] == "/":
            path = path[1:]
        file_path = join(_SUZIEQ_PATH, path, self._file_name)
        if not isfile(file_path):
            return None, self.getError("404.page_not_found")
        with open(file_path, "r") as f:
            return json.loads(f.read()), None

    def getError(self, error):
        error_path = join(_ERRORS_PATH, error)
        if not isfile(error_path):
            return 500, "Internal error"
        error_code = int(error.split(".")[0])
        with open(error_path, "r") as f:
            return error_code, f.read()

    async def getDevices(
        self,
        request: Request,
        tag: Optional[str] = Query(None, max_length=50),
        limit: Optional[int] = Query(None),
        offset: Optional[int] = Query(None),
    ):

        token = request.headers.get("authorization", None)
        if not token:
            error_code, error = self.getError("403.no_token")
            raise HTTPException(status_code=error_code, detail=error)
        token = token.split()[1]
        if token not in self._valid_tokens:
            error_code, error = self.getError("403.invalid_token")
            raise HTTPException(status_code=error_code, detail=error)

        result = self.getData("/api/dcim/devices/")
        if result[1] is not None:
            error_code, error = result[1]
            raise HTTPException(status_code=error_code, detail=error)
        in_devices = result[0].get("results", [])
        if tag == "null":
            tag = None
        devices = []
        for d in in_devices:
            # if tag is None the function must return all the devices
            if tag is None or (d.get("tags", []) and len(
                list(filter(lambda t: t["name"] == tag, d.get("tags", [])))
            ) > 0):
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
                res["previous"] = \
                    "/api/dcim/devices/?limit={}&offset={}&tag={}"\
                    .format(limit, offset - limit, tag)

        if len(devices) > limit:
            devices = devices[:limit]
            res["next"] = "/api/dcim/devices/?limit={}&offset={}&tag={}"\
                .format(limit, offset + limit, tag)

        res["results"] = devices
        return res

    async def getToken(self, request: Request):
        valid_credentials = {"username": "admin", "password": "admin"}
        credentials = await request.json()
        if credentials != valid_credentials:
            error_code, error = self.getError("403.invalid_credentials")
            raise HTTPException(status_code=error_code, detail=error)

        result = self.getData("/api/users/tokens/provision/")
        if result[1] is not None:
            error_code, error = result[1]
            raise HTTPException(status_code=error_code, detail=error)

        tokens = result[0]
        return tokens[randint(0, len(tokens)-1)]

    async def server_kill(self):
        kill(getpid(), signal.SIGTERM)


def rest_main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-c",
        "--config",
        help="REST server configuration file",
        required=True
    )

    args = parser.parse_args()

    config_file = args.config
    if not isfile(config_file):
        raise ValueError("The configuration file doesn't exists")

    with open(config_file, "r") as f:
        config_data = yaml.safe_load(f.read())

    nra = NetboxRestApp(config_data)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    uvicorn.run(nra.app, host=nra.ip_addr, port=nra.port)


if __name__ == "__main__":
    rest_main()
