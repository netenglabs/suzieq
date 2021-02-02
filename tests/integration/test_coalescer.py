import pytest
import os
from tests.conftest import get_dummy_config
import yaml
from tempfile import TemporaryDirectory, NamedTemporaryFile
from distutils.dir_util import copy_tree
from subprocess import check_output
from importlib.util import find_spec

from .utils import assert_df_equal


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
    tmpdir = TemporaryDirectory()

    # Copy the directory we want to copy
    copy_tree(pq_dir, tmpdir.name)

    config = get_dummy_config()
    config['data-directory'] = f'{tmpdir.name}/'

    tmpfile = NamedTemporaryFile(suffix='.yml')
    with open(tmpfile.name, 'w') as f:
        yaml.dump(config, f)

    return tmpdir, tmpfile


def _coalescer_cleanup(tmpdir: TemporaryDirectory,
                       tmpfile):
    """Cleanup the test dir and such

    :param tmpdir: TemporaryDirectory, the temp parquet dir
    :param tmpfile: tempfile._TemporaryFileWrapper, the temp config file
    :returns: Nothing
    :rtype: None

    """
    assert(isinstance(tmpdir, TemporaryDirectory))
    tmpdir.cleanup()
    assert(not os.path.exists(tmpdir.name))

    assert(not isinstance(tmpfile, str))
    tmpfile.close()             # This should delete the file too
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

    tmpdir, tmpfile = _coalescer_init(pq_dir)

    from suzieq.sqobjects.tables import TablesObj
    from suzieq.sqobjects.path import PathObj

    tablesobj = TablesObj(config_file=tmpfile.name)
    pre_tables_df = tablesobj.get()
    pathobj = PathObj(config_file=tmpfile.name)
    pre_path_df = pathobj.get(
        namespace=[namespace], source=path_src, dest=path_dest)

    # Now lets coalesce the data
    sq_path = os.path.dirname(find_spec('suzieq').loader.path)

    coalescer_bin = f'{sq_path}/utilities/sq-coalescer.py'
    coalescer_args = f'-c {tmpfile.name} --run-once'.split()

    coalescer_cmd_args = [coalescer_bin] + coalescer_args
    try:
        _ = check_output(coalescer_cmd_args)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

    # Check that the coalesced directory exists
    # We're assuming the coalesced dir is inside the same root dir as the
    # original
    coalesced_dir = f'{tmpdir.name}/coalesced'
    assert(os.path.exists(coalesced_dir))

    # Lets verify there are no files left in the main parquet dir

    original_files = []
    dirs = os.listdir(tmpdir.name)
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

    post_tables_df = tablesobj.get()
    assert_df_equal(pre_tables_df, post_tables_df, None)

    post_path_df = pathobj.get(
        namespace=[namespace], source=path_src, dest=path_dest)
    assert_df_equal(pre_path_df, post_path_df, None)

    _coalescer_cleanup(tmpdir, tmpfile)


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
