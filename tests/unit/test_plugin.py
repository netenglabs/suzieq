import os

import pytest

from suzieq.shared.context import SqContext
from suzieq.shared.schema import Schema
from suzieq.sqobjects.basicobj import SqObject
import suzieq.sqobjects.basicobj as basicobj
from suzieq.engines.base_engine import SqEngineObj
from suzieq.sqobjects.vlan import VlanObj
from suzieq.sqobjects import get_tables, get_sqobject
from suzieq.engines import get_sqengine
from suzieq.db import get_sqdb_engine
from suzieq.shared.exceptions import DBNotFoundError


@pytest.mark.plugin
def test_plugin():
    """Ensure that we can get the plugins we need correctly
    """

    # Validate base engine stuff works for sqobjects
    assert SqObject.get_plugins()
    assert SqObject.get_plugins('vlan')['vlan'] == VlanObj
    assert not SqObject.get_plugins('foobar')

    # Validate engine stuff works for engines
    assert SqEngineObj.get_plugins()
    assert SqEngineObj.get_plugins('pandas')
    assert not SqEngineObj.get_plugins('foobar')

    # Now validate the APIs
    assert get_tables()
    assert get_sqobject('vlan') == VlanObj
    with pytest.raises(ModuleNotFoundError):
        get_sqobject('foobar')

    assert get_sqengine('pandas', '')
    with pytest.raises(ModuleNotFoundError):
        get_sqengine('foobar', '')

    assert get_sqengine('pandas', 'vlan')
    with pytest.raises(ModuleNotFoundError):
        get_sqengine('pandas', 'foobar')

    assert get_sqdb_engine({}, 'foobar', 'parquet', None)
    assert get_sqdb_engine({'foobar': 'parquet'}, 'foobar', None, None)

    with pytest.raises(DBNotFoundError):
        get_sqdb_engine({'db': {'foobar': 'bar'}}, 'foobar', None, None)


def test_rest_engine_initializes_context_from_config(monkeypatch):
    """Per-command rest engine selection should load REST config."""

    class DummyEngine:
        def __init__(self, obj):
            self.obj = obj

    cfg = {
        'schema-directory': os.path.abspath('suzieq/config/schema'),
        'rest': {
            'API_KEY': 'my-api-key',
            'address': '127.0.0.1',
            'port': 8000,
            'no-https': True,
        },
    }
    ctxt = SqContext(cfg=cfg)
    ctxt.schemas = Schema(cfg['schema-directory'])

    monkeypatch.setattr(
        basicobj, 'get_sqengine', lambda engine, table: lambda obj: DummyEngine(obj))

    obj = VlanObj(context=ctxt, engine_name='rest')

    assert obj.ctxt.engine == 'pandas'
    assert obj.ctxt.rest_api_key == 'my-api-key'
    assert obj.ctxt.rest_server_ip == '127.0.0.1'
    assert obj.ctxt.rest_server_port == 8000
    assert obj.ctxt.rest_transport == 'http'
