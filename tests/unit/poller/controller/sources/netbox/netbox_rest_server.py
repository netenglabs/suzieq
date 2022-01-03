import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.routing import APIRoute

_NETBOX_DATA_DIR = 'tests/unit/poller/controller/sources/data/netbox/'\
    'rest_server/'
_ERRORS_PATH = _NETBOX_DATA_DIR + 'errors.yaml'


class NetboxRestApp:
    """Netbox REST server emulator class
    """

    def __init__(self, ip: str = '127.0.0.1', port: int = 9000,
                 name: str = 'netbox0') -> None:
        self.ip_addr = ip
        self.port = port
        self.netbox_name = name
        self._device_path = _NETBOX_DATA_DIR + self.netbox_name + '.json'

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
                )
            ]
        )

    def getData(self, path: str) -> Tuple[Any, Tuple[int, str]]:
        """Return the content of path or an error

        There it is an error if the content of the returned tuple in
        position 1 is not None

        Args:
            path (str): path from which return the data

        Returns:
            Tuple[Any, Tuple[int, str]]: return the content of path
            or the 'page not found' error if the path doesn't exists
        """
        file_path = Path(path)
        if not file_path.is_file():
            return None, self.getError("page_not_found")
        with open(file_path, "r") as f:
            return json.loads(f.read()), None

    def getError(self, error: str) -> Tuple[int, str]:
        """Return the error code and the error message corresponding to the input
        input key

        If the input error a generic 500(Internal error) is returned

        Args:
            error (str): error key identifier

        Returns:
            Tuple[int, str]: error_code, error_message
        """
        if error not in self._errors:
            return 500, "Internal error"
        return self._errors[error]['code'], self._errors[error]['message']

    async def getDevices(
        self,
        request: Request,
        tag: Optional[str] = Query(None, max_length=50),
        limit: Optional[int] = Query(None),
        offset: Optional[int] = Query(None),
    ) -> Dict:
        """Read the devices from file and return them in the same way as
        Netbox does

        Args:
            request (Request): http request
            tag (Optional[str], optional): tag to search.
            Defaults to Query(None, max_length=50).

            limit (Optional[int], optional): the number of devices to return.
            Defaults to Query(None).

            offset (Optional[int], optional): how many device to skip.
            Defaults to Query(None).

        Raises:
            HTTPException: Error during device retrieving

        Returns:
            Dict: the returned dictionary is composed by:
                'count': the total number of devices (also over limit)
                'next': if limit and/or offset are set, this field contains the
                url to get the next devices
                'prev': if limit and/or offset are set, this field contains the
                url to get the previous devices
                'results': the current list of devices
        """
        token = request.headers.get("authorization", None)
        if not token:
            error_code, error = self.getError("no_token")
            raise HTTPException(status_code=error_code, detail=error)
        token = token.split()[1]
        if token not in self._valid_tokens:
            error_code, error = self.getError("invalid_token")
            raise HTTPException(status_code=error_code, detail=error)

        result = self.getData(self._device_path)
        if result[1]:
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
                    f"Select a valid choice. {tag} is not one of the "
                    "available choices."
                ]
            }

        if not limit:
            # default netbox limit is 50
            limit = 50

        if not offset:
            offset = 0

        res = {
            "count": len(devices),
            "previous": None,
            "next": None
        }

        server_host = f'http://{self.ip_addr}:{self.port}'

        if offset != 0:
            devices = devices[offset:]
            if offset - limit < 0:
                res["previous"] = f"{server_host}/api/dcim/devices/"\
                    f"?limit={limit}&tag={tag}"
            else:
                res["previous"] = f"{server_host}/api/dcim/devices/"\
                    f"?limit={limit}&offset={offset - limit}&tag={tag}"

        if len(devices) > limit:
            devices = devices[:limit]
            res["next"] = f"{server_host}/api/dcim/devices/"\
                f"?limit={limit}&offset={offset + limit}&tag={tag}"

        res["results"] = devices
        return res

    def start(self):
        """Start the REST server
        """
        uvicorn.run(self.app, host=self.ip_addr, port=self.port)
