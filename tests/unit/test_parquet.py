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
        engine.get_table_df(create_context_config, get_schemas, table='system', **fields)
        
        
good_tables = tables[:]
good_tables[2] = pytest.param(good_tables[2], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # evpnVni
good_tables[9] = pytest.param(good_tables[9], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # # ospfIf
good_tables[10] = pytest.param(good_tables[10], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # ospfNbr


@pytest.mark.engines
@pytest.mark.parametrize('table', good_tables)
def test_get_data(create_context_config, get_schemas, tmp_path, table):
    """goes through each table and gets the default output and does file comparison with previous known good ouput"""
    out = _get_data_from_table(create_context_config, get_schemas, table)
    _compare_all_fields(create_context_config, get_schemas, tmp_path, table, out)
    _compare_key_fields(create_context_config, get_schemas, table, out)

@pytest.mark.engines
@pytest.mark.parametrize('table', good_tables)
def test_get_all_data(create_context_config, get_schemas, tmp_path, table):
    """goes through each table and gets the default output and does file comparison with previous known good ouput"""
    out = _get_data_from_table(create_context_config, get_schemas, table, {'columns': ['*']})
    #_compare_all_fields(create_context_config, get_schemas, tmp_path, table, out)
    _compare_key_fields(create_context_config, get_schemas, table, out)



@pytest.mark.engines
@pytest.mark.parametrize('table', good_tables)
def test_latest_view_data(create_context_config, get_schemas, tmp_path, table):
    out = _get_data_from_table(create_context_config, get_schemas, table, {'view': 'latest'})
    _compare_key_fields(create_context_config, get_schemas, table, out)



def _compare_all_fields(cfg, sch, path, table, data):
    """this is a complicated. doing both a file comparison as well as pandas, because I dont' know' \
       which is the better approach overall"""                                                                                                 ''

    sample_df, sample_csv = _get_sample_df(cfg, table)

    schema = SchemaForTable(table, schema=sch)

    data, sample_df = _cleanup_dataframes_for_io(data, sample_df, schema)

    txt = path / f"{table}.txt"  # write txt for easier for humans to read
    csv = path / f"{table}.csv"
    txt.write_text(data.to_string())
    csv.write_text(data.to_csv())

    testing.assert_frame_equal(data, sample_df, check_dtype=True, check_categorical=False)
    assert (cmp(sample_csv, csv))


def _compare_key_fields(cfg, sch,  table, df_one):
    """ compare two dataframes using just the key columns
      the point is that if something else there are duplicates, then we don't compare those changes,
      those are temporal and that's ok
    """

    schema = SchemaForTable(table, schema=sch)
    df_two, sample_csv = _get_sample_df(cfg, table)
    df_one, df_two = _cleanup_dataframes_for_io(df_one, df_two, schema)

    k_fields = schema.key_fields()
    fields = schema.sorted_display_fields()
    df_one = df_one[k_fields].drop_duplicates(subset=k_fields, keep='last')
    df_two = df_two[k_fields].drop_duplicates(subset=k_fields, keep='last')

    testing.assert_frame_equal(df_one, df_two, check_dtype=True, check_categorical=False)


def _get_sample_df(cfg, table):
    sample_dir = Path("./tests/samples") / cfg['test_set']
    sample_csv = sample_dir / f"{table}.csv"

    sample_df = read_csv(sample_csv, index_col=0)
    return sample_df, sample_csv

def _cleanup_dataframes_for_io(computed_df, readin_df, schema):
    """ reading in from a written out dataframe does not get us back a useable dataframe
      so we must do some work
     readin_df is the one that is read from text
     computed_df is the one computed from the engine
     """
    assert isinstance(schema, SchemaForTable)
    readin_df['timestamp'] = to_datetime(readin_df['timestamp'])
    readin_df = readin_df.fillna('')

    # just reading in does not set all the types of the columns correctly
    # TODO: do this by schema types, rather than this way

    for col in readin_df.columns:
        if col in computed_df:
            readin_df[col] = readin_df[col].astype(computed_df[col].dtype.name)

    # for things that are text lists, we have to do some manipulation to get them back to their original structure
    for col in schema.array_fields:
        if col in readin_df:
            readin_df[col] = readin_df[col].str.replace('\[ ', '[').str.replace(' ', ', ')
            readin_df[col] = readin_df[col].apply(lambda x: literal_eval(x) if x else x)
            readin_df[col] = readin_df[col].fillna('')
            computed_df[col] = computed_df[col].apply(lambda x: '' if len(x) == 0 else x)  # replace empty list with nan so that reading later makes sense

    return computed_df, readin_df


def _get_data_from_table(cfg, sch, table, update_fields=None):
    if update_fields:
        assert isinstance(update_fields, dict)
    engine = SqPandasEngine()
    fields = {f: '' for f in required_fields}
    if update_fields:
        fields.update(update_fields)
    out = engine.get_table_df(cfg, sch, table=table, **fields)
    return out
