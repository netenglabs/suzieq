# this will test the parquet / pyarrow engine
# not clear if it's an integration test or something else
# TODO
#  test reading and writing. this is just focused on reading for now
#

import pytest
from pathlib import Path
from filecmp import cmp

from suzieq.engines.pandas.engine import SqPandasEngine

from tests.conftest import tables

fields = ['start_time', 'end_time', 'view', 'sort_fields']


@pytest.mark.engines
def test_bad_table_name(create_context_config, get_schemas):
    engine = SqPandasEngine()
    used_fields = {f: '' for f in fields}
    with pytest.raises(ValueError):
        engine.get_table_df(create_context_config, get_schemas, table='bad_table', **used_fields)


@pytest.mark.engines
@pytest.mark.parametrize('field', fields)
def test_required_fields(create_context_config, get_schemas, field):
    """make sure each of these is still required"""
    engine = SqPandasEngine()
    used_fields = {f: '' for f in fields if f != field}
    with pytest.raises(KeyError):
        engine.get_table_df(create_context_config, get_schemas, table='sysmtem', **used_fields)
        
        
good_tables = tables[:]
good_tables[2] = pytest.param(good_tables[2], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # evpnVni
good_tables[9] = pytest.param(good_tables[9], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # # ospfIf
good_tables[10] = pytest.param(good_tables[10], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # ospfNbr


@pytest.mark.engines
@pytest.mark.parametrize('table', good_tables)
def test_get_data(create_context_config, get_schemas, tmp_path, table):
    """this goes through each table and gets the default output and does file comparison with previous known good ouput"""
    engine = SqPandasEngine()
    used_fields = {f: '' for f in fields}
    out = engine.get_table_df(create_context_config, get_schemas, table=table, **used_fields)

    assert out.size > 0
    txt = tmp_path / f"{table}.txt"  # write txt for easier for humans to read
    csv = tmp_path / f"{table}.csv"
    txt.write_text(out.to_string())
    csv.write_text(out.to_csv())
    sample_dir = Path("./tests/samples") / create_context_config['test_set']
    sample_text = sample_dir / f"{table}.txt"
    sample_csv = sample_dir / f"{table}.csv"
    assert(cmp(sample_csv, csv))


