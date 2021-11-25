import uvicorn
from typing import Optional
from fastapi import FastAPI, Query

app = FastAPI()

def rest_main():
    uvicorn.run(app, host='', port=9000)

@app.get("/api/dcim/devices/")
async def getDevices(tag: Optional[str] = Query(None, max_length=50)):
    return {"message": tag or "no_query"}

@app.post("/api/users/tokens/provision/")
async def getToken():
    return {"token":"token-value"}

if __name__ == "__main__":
    rest_main()