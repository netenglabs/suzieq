# this will test the parquet / pyarrow engine
# not clear if it's an integration test or something else
# TODO
#  test reading and writing. this is just focused on reading for now
#

import pytest
from pathlib import Path
from filecmp import cmp
from pandas import read_csv, DataFrame, to_datetime, testing
from ast import literal_eval
import numpy as np

from suzieq.engines.pandas.engine import SqPandasEngine
from suzieq.utils import SchemaForTable

from tests.conftest import tables

required_fields = ['start_time', 'end_time', 'view', 'sort_fields']

@pytest.mark.engines
def test_bad_table_name(create_context_config, get_schemas):
    with pytest.raises(ValueError):
        _get_data_from_table(create_context_config, get_schemas, 'bad_table')

@pytest.mark.engines
@pytest.mark.parametrize('field', required_fields)
def test_required_fields(create_context_config, get_schemas, field):
    """make sure each of these is still required"""
    engine = SqPandasEngine()
    fields = {f: '' for f in required_fields if f != field}
    with pytest.raises(KeyError):
        engine.get_table_df(create_context_config, get_schemas, table='sysmtem', **fields)
        
        
good_tables = tables[:]
good_tables[2] = pytest.param(good_tables[2], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # evpnVni
good_tables[9] = pytest.param(good_tables[9], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # # ospfIf
good_tables[10] = pytest.param(good_tables[10], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # ospfNbr


@pytest.mark.engines
@pytest.mark.parametrize('table', good_tables)
def test_get_data(create_context_config, get_schemas, tmp_path, table):
    """goes through each table and gets the default output and does file comparison with previous known good ouput"""
    out = _get_data_from_table(create_context_config, get_schemas, table)
    _test_and_compare(create_context_config, get_schemas, tmp_path, table, out)


@pytest.mark.engines
@pytest.mark.parametrize('table', good_tables)
@pytest.mark.xfail(reason='not yet')
def test_start_time_data(create_context_config, get_schemas, tmp_path, table):
    out = _get_data_from_table(create_context_config, get_schemas, table, {'view': 'latest'})
    _test_and_compare(create_context_config, get_schemas, tmp_path, table, out)


def _test_and_compare(cfg, sch, path, table, data):
    """this is a complicated. doing both a file comparison as well as pandas, because I dont' know' \
       which is the better approach overall"""                                                                                                 ''
    assert isinstance(data, DataFrame)
    assert data.size > 0
    sample_dir = Path("./tests/samples") / cfg['test_set']
    sample_csv = sample_dir / f"{table}.csv"

    sample_df = read_csv(sample_csv, index_col=0)

    sample_df['timestamp'] = to_datetime(sample_df['timestamp'])
    sample_df = sample_df.fillna('')

    # just reading in does not set all the types of the columns correctly
    # TODO: do this by schema types, rather than this way
    for col in sample_df.columns:
        sample_df[col] = sample_df[col].astype(data[col].dtype.name)

    schema = SchemaForTable(table, schema=sch)

    # for things that are text lists, we have to do some manipulation to get them back to their original structure
    for col in schema.array_fields:
        if col in sample_df:
            sample_df[col] = sample_df[col].str.replace('\[ ', '[').str.replace(' ', ', ')
            sample_df[col] = sample_df[col].apply(lambda x: literal_eval(x) if x else x)
            sample_df[col] = sample_df[col].fillna('')
            data[col] = data[col].apply(lambda x: '' if len(x) == 0 else x)  # replace empty list with nan so that reading later makes sense

    txt = path / f"{table}.txt"  # write txt for easier for humans to read
    csv = path / f"{table}.csv"
    txt.write_text(data.to_string())
    csv.write_text(data.to_csv())
    assert (cmp(sample_csv, csv))

    testing.assert_frame_equal(data, sample_df, check_dtype=True, check_categorical=False)


def _get_data_from_table(cfg, sch, table, update_fields=None):
    engine = SqPandasEngine()
    fields = {f: '' for f in required_fields}
    if update_fields:
        fields.update(update_fields)
    out = engine.get_table_df(cfg, sch, table=table, **fields)
    return out
