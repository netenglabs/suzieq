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
