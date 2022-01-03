import argparse
import asyncio
import json
import signal
from os import getpid, kill
from typing import Optional
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.routing import APIRoute

_NETBOX_DATA_DIR = 'tests/unit/poller/controller/sources/data/netbox/'\
    'rest_server/'
_DEVICES_PATH = _NETBOX_DATA_DIR + 'netbox1.json'
_ERRORS_PATH = _NETBOX_DATA_DIR + 'errors.yaml'
_TOKENS_PATH = _NETBOX_DATA_DIR + 'tokens.json'


class NetboxRestApp:
    def __init__(self, ip: str = '127.0.0.1', port: int = 9000) -> None:
        self.ip_addr = ip
        self.port = port
        # self.netbox_name = config_data.get("netbox_name", "")
        # if not self.netbox_name:
        #     raise ValueError("The field <netbox_name> must be set")
        # self._file_name = self.netbox_name + ".json"

        self._valid_tokens = ['MY-TOKEN']

        errors_file = Path(_ERRORS_PATH)
        if not errors_file.is_file():
            raise RuntimeError(f"No errors file at {_ERRORS_PATH}")
        with open(errors_file, 'r') as f:
            self._errors = yaml.safe_load(f.read())

        self.app = FastAPI(
            routes=[
                APIRoute(
                    "/api/dcim/devices/",
                    self.getDevices,
                    status_code=200,
                    methods=["GET"]
                ),
                APIRoute(
                    "/kill",
                    self.server_kill,
                    status_code=200,
                    methods=["POST"]
                )
            ]
        )

    def getData(self, path: str):
        file_path = Path(path)
        if not file_path.is_file():
            return None, self.getError("page_not_found")
        with open(file_path, "r") as f:
            return json.loads(f.read()), None

    def getError(self, error: str):
        if error not in self._errors:
            return 500, "Internal error"
        return self._errors[error]['code'], self._errors[error]['text']

    async def getDevices(
        self,
        request: Request,
        tag: Optional[str] = Query(None, max_length=50),
        limit: Optional[int] = Query(None),
        offset: Optional[int] = Query(None),
    ):

        token = request.headers.get("authorization", None)
        if not token:
            error_code, error = self.getError("no_token")
            raise HTTPException(status_code=error_code, detail=error)
        token = token.split()[1]
        if token not in self._valid_tokens:
            error_code, error = self.getError("invalid_token")
            raise HTTPException(status_code=error_code, detail=error)

        result = self.getData(_DEVICES_PATH)
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

    async def server_kill(self):
        kill(getpid(), signal.SIGTERM)

    def start(self):
        uvicorn.run(self.app, host=self.ip_addr, port=self.port)

    async def stop(self):
        await self.server_kill()

