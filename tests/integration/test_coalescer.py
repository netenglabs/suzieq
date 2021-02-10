import pytest
import asyncio
import os
from tests.conftest import get_dummy_config
import yaml
from tempfile import TemporaryDirectory, NamedTemporaryFile
from distutils.dir_util import copy_tree
from dateparser import parse
import pytz
import pandas as pd
import numpy as np
from importlib.util import find_spec
from subprocess import check_output

from .utils import Yaml2Class, assert_df_equal
from suzieq.sqobjects import get_sqobject
from suzieq.utils import humanize_timestamp, Schema, SchemaForTable
from suzieq.utils import load_sq_config
from suzieq.db import get_sqdb_engine, do_coalesce


def _verify_coalescing(datadir):
    '''Verify coalescing worked.

    This is a simple verification. It verifies that post-coalescing, there
    are no files left in the original parquet directory and there are
    files in the coalesced directory

    :param datadir: the parquet dir to check
    '''
    # Check that the coalesced directory exists
    # We're assuming the coalesced dir is inside the same root dir as the
    # original
    coalesced_dir = f'{datadir.name}/coalesced'
    assert(os.path.exists(coalesced_dir))

    # Lets verify there are no files left in the main parquet dir

    original_files = []
    dirs = os.listdir(datadir.name)
    dirs = [x for x in dirs if x not in ['coalesced', '_archived']]
    for dir in dirs:
        for _, _, files in os.walk(dir):
            if files:
                original_files.extend(files)
    assert(len(original_files) == 0)

    # And verify there are files in the coalesced dir
    coalesced_files = []
    for _, _, files in os.walk(coalesced_dir):
        if files:
            coalesced_files.extend(files)

    assert(len(coalesced_files))


def _coalescer_init(pq_dir: str) -> (TemporaryDirectory, NamedTemporaryFile):
    """Basic Coalescer test

    :param pq_dir: the input parquet dir to be copied, this is the root of the
                   parquet dir (tests/data/nxos/parquet-out, for example)
    :returns: temporary dir where the parquet data has been copied to
    :rtype: TemporaryDirectory
    :returns: Temporary config file
    :rtype: NamedTemporaryFile

    """

    # Create a temp dir
    temp_dir = TemporaryDirectory()

    # Copy the directory we want to copy
    copy_tree(pq_dir, temp_dir.name)

    config = get_dummy_config()
    config['data-directory'] = f'{temp_dir.name}/'

    tmpfile = NamedTemporaryFile(suffix='.yml', delete=False)
    with open(tmpfile.name, 'w') as f:
        yaml.dump(config, f)

    return temp_dir, tmpfile


def _coalescer_cleanup(temp_dir: TemporaryDirectory,
                       tmpfile):
    """Cleanup the test dir and such

    :param temp_dir: TemporaryDirectory, the temp parquet dir
    :param tmpfile: tempfile._TemporaryFileWrapper, the temp config file
    :returns: Nothing
    :rtype: None

    """
    assert(isinstance(temp_dir, TemporaryDirectory))
    temp_dir.cleanup()
    assert(not os.path.exists(temp_dir.name))

    assert(not isinstance(tmpfile, str))
    tmpfile.close()             # This should delete the file too
    os.unlink(tmpfile.name)
    assert(not os.path.exists(tmpfile.name))


def _coalescer_basic_test(pq_dir, namespace, path_src, path_dest):
    """Basic coalescer test

    Copy the parquet dir from the directory provided to a temp dir,
    coalesce and ensure that everything looks the same. This second
    part is done by ensuring table show looks the same before and
    after coalescing, and since we're assuming a run-once parquet input,
    there shouldn't be any duplicate entries that are being coalesced.

    We also run path before and after coalescing. path encompasseds many
    different tables and so with a single command we test multiple tables
    are correctly rendered.

    :param pq_dir: The original parquet dir
    :param namespace: The namespace to be used for checking info
    :param path_src: The source IP of the path
    :param path_dest: The destination IP of the path
    :returns:
    :rtype:

    """

    temp_dir, tmpfile = _coalescer_init(pq_dir)

    from suzieq.sqobjects.tables import TablesObj
    from suzieq.sqobjects.path import PathObj

    tablesobj = TablesObj(config_file=tmpfile.name)
    pre_tables_df = tablesobj.get()
    pathobj = PathObj(config_file=tmpfile.name)
    pre_path_df = pathobj.get(
        namespace=[namespace], source=path_src, dest=path_dest)

    cfg = load_sq_config(config_file=tmpfile.name)

    do_coalesce(cfg, None)
    _verify_coalescing(temp_dir)

    post_tables_df = tablesobj.get()
    assert_df_equal(pre_tables_df, post_tables_df, None)

    post_path_df = pathobj.get(
        namespace=[namespace], source=path_src, dest=path_dest)
    assert_df_equal(pre_path_df, post_path_df, None)

    _coalescer_cleanup(temp_dir, tmpfile)


@pytest.mark.coalesce
@pytest.mark.parametrize("pq_dir, namespace, path_src, path_dest",
                         [pytest.param('tests/data/nxos/parquet-out', 'nxos',
                                       '172.16.1.101', '172.16.2.201',
                                       marks=pytest.mark.nxos)])
def test_basic_single_namespace(pq_dir, namespace, path_src, path_dest):
    _coalescer_basic_test(pq_dir, namespace, path_src, path_dest)


@pytest.mark.coalesce
@pytest.mark.cumulus
@pytest.mark.parametrize("pq_dir, namespace, path_src, path_dest",
                         [('tests/data/multidc/parquet-out', 'dual-evpn',
                           '172.16.1.101', '172.16.2.104')])
def test_basic_multi_namespace(pq_dir, namespace, path_src, path_dest):
    _coalescer_basic_test(pq_dir, namespace, path_src, path_dest)


@pytest.mark.coalesce
def test_coalescer_bin(run_sequential):
    '''Verify the sq-coalescer bin works'''

    temp_dir, tmpfile = _coalescer_init(
        'tests/data/basic_dual_bgp/parquet-out')

    sq_path = os.path.dirname(find_spec('suzieq').loader.path)
    coalescer_bin = f'{sq_path}/utilities/sq-coalescer.py'
    coalescer_args = f'-c {tmpfile.name} --run-once'.split()
    coalescer_cmd_args = [coalescer_bin] + coalescer_args

    _ = check_output(coalescer_cmd_args)

    _verify_coalescing(temp_dir)

    _coalescer_cleanup(temp_dir, tmpfile)


async def _run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    return proc.returncode


async def _run_multiple_coalescer(coalescer_cmd_args):
    rc = await asyncio.gather(
        _run(coalescer_cmd_args),
        _run(coalescer_cmd_args))

    # One of the run calls must return a 0 and the other 1
    # because the second one to run will find the lock
    assert(rc[0] != rc[1])


@pytest.mark.coalesce
@pytest.mark.asyncio
async def test_single_instance_run(run_sequential):
    '''Verify that only a single instance of the coalescer is running'''

    temp_dir, tmpfile = _coalescer_init(
        'tests/data/basic_dual_bgp/parquet-out')

    sq_path = os.path.dirname(find_spec('suzieq').loader.path)
    coalescer_bin = f'{sq_path}/utilities/sq-coalescer.py'
    coalescer_args = f'-c {tmpfile.name} --run-once'
    coalescer_cmd_args = f'{coalescer_bin} {coalescer_args}'

    await _run_multiple_coalescer(coalescer_cmd_args)

    _coalescer_cleanup(temp_dir, tmpfile)


def _process_transform_set(action, mod_df, changed_fields):
    """Process a set(action) entry from the transform file

    This routine modifies the dataframe with the action specified
    :param match_entry: dict, the entry containing a match and set
    :returns:
    :rtype:

    """
    for field in action:
        if field not in mod_df.columns:
            break
        changed_fields.add(field)
        if field == "timestamp":
            if action[field].startswith('+'):
                delta = pd.Timedelta(action[field][1:])
                mod_df[field] += delta
            else:
                mod_df[field] = parse(action[field]) \
                    .astimezone(pytz.utc).timestamp()*1000
                mod_df[field] = pd.to_datetime(
                    mod_df[field], unit='ms')
        else:
            mod_df[field] = action[field]


def _write_verify_transform(mod_df, table, dbeng, schema, config_file,
                            query_str_list, changed_fields):
    """Write and verify that the written data is present

    :param mod_df: pd.DataFrame, the modified dataframe to write
    :param table: str, the name of the table to write
    :param dbeng: SqParquetDB, pointer to DB class to write/read
    :param schema: SchemaForTable, Schema of data to be written
    :param config_file: str, Filename where suzieq config is stored
    :param query_str_list: List[str], query string if any to apply to data for
                           verification check
    :param changed_fields: set, list of changed fields to verify
    :returns: Nothing
    :rtype:

    """
    mod_df = mod_df.reset_index(drop=True)
    mod_df.timestamp = mod_df.timestamp.astype(np.int64)
    mod_df.timestamp = mod_df.timestamp//1000000
    mod_df.sqvers = mod_df.sqvers.astype(str)
    dbeng.write(table, 'pandas', mod_df, False, schema.get_arrow_schema(),
                None)

    # Verify that what we wrote is what we got back
    mod_df.sqvers = mod_df.sqvers.astype(float)

    tblobj = get_sqobject(table)
    post_read_df = tblobj(config_file=config_file).get(
        columns=schema.fields)

    assert(not post_read_df.empty)
    # If the data was built up as a series of queries, we have to
    # apply the queries to verify that we have what we wrote
    dfconcat = None
    if query_str_list:
        for qstr in query_str_list:
            qdf = post_read_df.query(qstr).reset_index(drop=True)
            assert(not qdf.empty)
            if dfconcat is not None:
                dfconcat = pd.concat([dfconcat, qdf])
            else:
                dfconcat = qdf

    if dfconcat is not None:
        qdf = dfconcat.set_index(schema.key_fields()) \
                      .sort_index()
    else:
        qdf = post_read_df.set_index(schema.key_fields()) \
                          .sort_index()

    mod_df = mod_df.set_index(schema.key_fields()) \
                   .query('~index.duplicated(keep="last")') \
                   .sort_index()

    mod_df.timestamp = humanize_timestamp(
        mod_df.timestamp, 'GMT')

    # We can't call assert_df_equal directly and so we
    # compare this way. The catch is if we accidentally
    # change some of the unchanged fields
    assert(mod_df.shape == qdf.shape)

    assert(not [x for x in mod_df.columns.tolist()
                if x not in qdf.columns.tolist()])

    assert((mod_df.index == qdf.index).all())

    assert_df_equal(mod_df[changed_fields].reset_index(),
                    qdf[changed_fields].reset_index(),
                    None)


@pytest.mark.coalesce
@pytest.mark.transform
@pytest.mark.parametrize(
    "input_file", [pytest.param('tests/integration/coalescer/file1.yml')]
)
def test_transform(input_file):
    to_transform = Yaml2Class(input_file)

    try:
        data_directory = to_transform.transform.data_directory
    except AttributeError:
        print('Invalid transformation file, no data directory')
        pytest.fail('AttributeError', pytrace=True)

    #  Make a copy of the data directory
    temp_dir, tmpfile = _coalescer_init(data_directory)

    cfg = load_sq_config(config_file=tmpfile.name)
    schemas = Schema(cfg['schema-directory'])

    for ele in to_transform.transform.transform:
        query_str_list = []
        # Each transformation has a record => write's happen per record
        for record in ele.record:
            changed_fields = set()
            new_df = pd.DataFrame()
            tables = [x for x in dir(record) if not x.startswith('_')]
            for table in tables:
                # Lets read the data in now that we know the table
                tblobj = get_sqobject(table)
                pq_db = get_sqdb_engine(cfg, table, None, None)
                columns = schemas.fields_for_table(table)
                mod_df = tblobj(config_file=tmpfile.name).get(
                    columns=columns)

                for key in getattr(record, table):
                    query_str = key.match
                    chg_df = pd.DataFrame()
                    if query_str != "all":
                        try:
                            chg_df = mod_df.query(query_str) \
                                           .reset_index(drop=True)
                        except Exception as ex:
                            assert(not ex)
                        query_str_list.append(query_str)
                    else:
                        chg_df = mod_df

                    _process_transform_set(key.set, chg_df, changed_fields)
                    if new_df.empty:
                        new_df = chg_df
                    elif not chg_df.empty:
                        new_df = pd.concat([new_df, chg_df])

                if new_df.empty:
                    continue

                # Write the records now
                _write_verify_transform(new_df, table, pq_db,
                                        SchemaForTable(table, schemas),
                                        tmpfile.name, query_str_list,
                                        changed_fields)

    # Now we coalesce and verify it works
    from suzieq.sqobjects.tables import TablesObj

    pre_table_df = TablesObj(config_file=tmpfile.name).get()
    do_coalesce(cfg, None)
    _verify_coalescing(temp_dir)

    post_table_df = TablesObj(config_file=tmpfile.name).get()
    assert_df_equal(pre_table_df, post_table_df, None)

    # Run additional tests on the coalesced data
    for ele in to_transform.transform.verify:
        table = [x for x in dir(ele) if not x.startswith('_')][0]
        tblobj = get_sqobject(table)

        for tst in getattr(ele, table):
            start_time = tst.test.get('start-time', '')
            end_time = tst.test.get('end-time', '')

            columns = tst.test.get('columns', ['default'])
            df = tblobj(config_file=tmpfile.name, start_time=start_time,
                        end_time=end_time).get(columns=columns)
            if not df.empty and 'query' in tst.test:
                query_str = tst.test['query']
                df = df.query(query_str).reset_index(drop=True)

            if 'assertempty' in tst.test:
                assert(df.empty)
            elif 'shape' in tst.test:
                shape = tst.test['shape'].split()
                if shape[0] != '*':
                    assert(int(shape[0]) == df.shape[0])
                if shape[1] != '*':
                    assert(int(shape[1]) == df.shape[1])
            else:
                assert(not df.empty)

    _coalescer_cleanup(temp_dir, tmpfile)
