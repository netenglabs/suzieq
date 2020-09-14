from typing import Optional
from fastapi import FastAPI

from suzieq.sqobjects import *


app = FastAPI()


@app.get("/v1//table/show")
async def read_table_show():
    return await read_table('get')
@app.get("/v1/table/{verb}")
async def read_table(verb: str):
    return getattr(tables.TablesObj(), verb)().to_json(orient="records")

@app.get("/v1/device/show")
async def read_device_show():
    return await read_device('get')
@app.get("/v1/device/{verb}")
async def read_device(verb: str, hostname: str = "",
                      start_time: str = "", end_time: str = "",
                      view: str = "latest", namespace: str = ""):
    return getattr(device.DeviceObj(hostname=hostname,
                                    start_time=start_time,
                                    end_time=end_time,
                                    view=view,
                                    namespace=namespace), verb)\
                                    (hostname=hostname, 
                                    namespace=namespace)\
                                    .to_json(orient="records")