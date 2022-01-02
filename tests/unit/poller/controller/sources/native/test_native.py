import pytest
import asyncio

from tests.unit.poller.controller.sources.utils import get_sample_config

@pytest.mark.native
@pytest.mark.source
@pytest.mark.parametrize('inv_path', _VALID_INVENTORY)
@pytest.mark.parametrize('result_path', _RESULT_PATH)
async def test_valid_native(inv_path: str, result_path: str):

    config = get_sample_config('native')
