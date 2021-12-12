import pytest
from suzieq.sqobjects.basicobj import SqObject
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
    try:
        get_sqobject('foobar')
        assert False
    except ModuleNotFoundError:
        pass

    assert get_sqengine('pandas', '')
    try:
        get_sqengine('foobar', '')
        assert False
    except ModuleNotFoundError:
        pass

    assert get_sqengine('pandas', 'vlan')
    try:
        get_sqengine('pandas', 'foobar')
        assert False
    except ModuleNotFoundError:
        pass

    assert get_sqdb_engine({}, 'foobar', 'parquet', None)
    try:
        get_sqdb_engine({'foobar': 'parquet'}, 'foobar', None, None)
    except DBNotFoundError:
        assert False, 'parquet DB engine not found in config'

    try:
        get_sqdb_engine({'db': {'foobar': 'bar'}}, 'foobar', None, None)
        assert False
    except DBNotFoundError:
        pass
