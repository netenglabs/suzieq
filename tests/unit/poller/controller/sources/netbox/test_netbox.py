import pytest
from multiprocessing import Process
import asyncio
import time

from tests.unit.poller.controller.sources.netbox.netbox_rest_server import \
    NetboxRestApp
from tests.unit.poller.controller.sources.utils import get_sample_config
from suzieq.poller.controller.source.netbox import Netbox

_SAMPLE_CONFIG = get_sample_config('netbox')

@pytest.fixture(scope="session", autouse=True)
def manager_rest_server():
    nra = NetboxRestApp()
    p = Process(target=nra.start)
    p.start()
    # wait for the REST server to start
    time.sleep(1)
    yield
    p.terminate()

@pytest.mark.source
@pytest.mark.asyncio
async def test_valid_inventory():
    config = _SAMPLE_CONFIG

    src = Netbox(config)
    await asyncio.wait_for(src.run(), 10)

    cur_inv = await asyncio.wait_for(src.get_inventory(), 5)
    assert len(cur_inv) == 2

