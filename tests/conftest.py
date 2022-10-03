import asyncio
import os
import pickle
import shlex
import sys
from subprocess import CalledProcessError, check_output
from tempfile import mkstemp
from typing import Dict, List
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest
import yaml
from filelock import FileLock

from nubia import Nubia
from suzieq.cli.sq_nubia_plugin import NubiaSuzieqPlugin

from suzieq.cli.sq_nubia_context import NubiaSuzieqContext
from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.poller.worker.services.service_manager import ServiceManager
from suzieq.shared.context import SqContext
from suzieq.shared.schema import Schema
from suzieq.shared.utils import load_sq_config
from suzieq.sqobjects import get_sqobject, get_tables

suzieq_cli_path = './suzieq/cli/sq_cli.py'
suzieq_rest_server_path = './suzieq/restServer/sq_rest_server.py'
suzieq_test_svc_dir = 'tests/unit/poller/worker/service_dir_test'

DATA_TO_STORE_FILE = 'tests/unit/poller/worker/utils/data_to_store.pickle'

DATADIR = ['tests/data/parquet']

IGNORE_SQCMDS = ['TopmemCmd', 'TopcpuCmd']


def get_sqcmds() -> Dict:
    sqcmds = SqTableCommand.get_plugins()
    sqcmds = {k: v for k, v in sqcmds.items() if k not in IGNORE_SQCMDS}
    return sqcmds


commands = [(x) for x in get_sqcmds()]

cli_commands = [(v.__command['name'])
                for k, v in get_sqcmds().items()]

TABLES = [t for t in get_tables() if t not in ['topmem', 'topcpu']]


@pytest.fixture(scope='session')
def get_cmd_object_dict() -> Dict:
    '''Get dict of command to cli_command object'''
    return {v.__command['name']: k
            for k, v in get_sqcmds().items()}


@pytest.fixture(scope='function')
def setup_nubia():
    '''Setup nubia for testing'''
    _setup_nubia()


@pytest.fixture()
# pylint: disable=unused-argument
def create_context_config(datadir: str =
                          './tests/data/parquet'):
    '''Create context config'''
    return


@pytest.fixture()
def get_table_data(table: str, datadir: str):
    '''Fixture to get all fields in table.

    This includes sqvers and any suppress field for DB check'''
    return _get_table_data(table, datadir)


def _get_table_data(table: str, datadir: str):
    '''Get all fields including sqvers and any suppress field for DB check'''
    if table in ['path', 'ospfIf', 'ospfNbr']:
        return pd.DataFrame()

    cfgfile = create_dummy_config_file(datadir=datadir)
    sqobj = get_sqobject(table)(config_file=cfgfile)
    cols = sqobj.schema.get_display_fields(['*'])

    # mackey is an internal field to be suppressed, however we need this field
    # for the testing purpose, manually add it
    if table == 'macs':
        cols.append('mackey')

    if table == "interface":
        df = sqobj.get(columns=cols, type=["all"])
    else:
        df = sqobj.get(columns=cols)

    if not df.empty and (table not in ['device', 'tables', 'network']):
        device_df = get_sqobject('device')(config_file=cfgfile) \
            .get(columns=['namespace', 'hostname', 'os'])

        assert not device_df.empty, 'empty device table'
        df = df.merge(device_df, on=['namespace', 'hostname']) \
            .fillna({'os': ''})

        if df.empty:
            pytest.fail('empty device table')

    return df


@pytest.fixture()
def get_table_data_cols(table: str, datadir: str, columns: List[str]):
    '''
    For the table and columns specified, get data, used for schema validation
    '''
    if table in ['path', 'ospfIf', 'ospfNbr', 'network']:
        return pd.DataFrame()

    cfgfile = create_dummy_config_file(datadir=datadir)
    df = get_sqobject(table)(config_file=cfgfile).get(columns=columns)

    return df


@ pytest.fixture
@ pytest.mark.asyncio
def init_services_default(event_loop):
    '''Mock setup of services'''
    configs = os.path.abspath(os.curdir) + '/suzieq/config/'
    schema = configs + 'schema/'
    mock_queue = Mock()
    service_manager = ServiceManager(None, configs, schema,
                                     mock_queue, 'forever')
    services = event_loop.run_until_complete(service_manager.init_services())
    return services


@ pytest.fixture
# pylint: disable=unused-argument
def run_sequential(tmpdir):
    """Uses a file lock to run tests using this fixture, sequentially

    """
    # pylint: disable=abstract-class-instantiated
    with FileLock('test.lock', timeout=120):
        yield()


@pytest.fixture
def data_to_write():
    """Retrieve a data structure to pass to an OuputWorker
    """
    return pickle.load(open(DATA_TO_STORE_FILE, 'rb'))


def get_async_task_mock(result=None):
    """Mock for the add tasks method in the Poller class
    """
    fn_res = asyncio.Future()
    fn_res.set_result(result)
    return MagicMock(return_value=fn_res)


def _setup_nubia():
    '''internal function to setup cli framework for testing'''

    # monkey patching -- there might be a better way
    plugin = NubiaSuzieqPlugin()
    plugin.create_context = create_context

    # this is just so that context can be created
    _ = Nubia(name='test', plugin=plugin)


def create_context():
    '''Create a SqContext object'''
    config = load_sq_config(config_file=create_dummy_config_file())
    context = NubiaSuzieqContext()
    context.ctxt = SqContext(cfg=config)
    context.ctxt.schemas = Schema(config["schema-directory"])
    return context


def create_dummy_config_file(
        datadir: str = './tests/data/parquet'):
    '''Create a dummy config file'''
    config = {'data-directory': datadir,
              'temp-directory': '/tmp/suzieq',
              'logging-level': 'WARNING',
              'test_set': 'basic_dual_bgp',  # an extra field for testing
              'rest': {'API_KEY': '68986cfafc9d5a2dc15b20e3e9f289eda2c79f40'},
              'analyzer': {'timezone': 'GMT'},
              }
    fd, tmpfname = mkstemp(suffix='.yml')
    f = os.fdopen(fd, 'w')
    f.write(yaml.dump(config))
    f.close()

    return tmpfname


def load_up_the_tests(folder):
    """reads the files from the samples directory and parametrizes the test"""
    tests = []

    for i in folder:
        if not i.path.endswith('.yml'):
            continue
        with open(i, 'r') as f:
            out = yaml.load(f.read(), Loader=yaml.BaseLoader)
            # The format of the YAML file assumed is as follows:
            # description: <string>
            # tests:
            #   - command: <sqcmd to execute in non-modal format
            #     data-directory: <where the data is present>, not used yet
            #     marks: <space separated string of marks to mark the test>
            #     output: |
            #       <json_output>
            #
            #   - command:
            #     ....
            if out and 'tests' in out:
                for t in out['tests']:
                    # We use tags to dynamically mark the parametrized test
                    # the marks MUST be registered in pytest.ini
                    markers = []
                    if 'marks' in t:
                        markers = [getattr(pytest.mark, x)
                                   for x in t['marks'].split()]
                    if 'xfail' in t:
                        except_err = None
                        if 'raises' in t['xfail']:
                            except_err = globals()['__builtins__'].get(
                                t['xfail']['raises'], None)

                        if except_err:
                            markers += [pytest.mark.xfail(
                                reason=t['xfail']['reason'],
                                raises=except_err)]
                        else:
                            if 'reason' in t['xfail']:
                                markers += [pytest.mark.xfail(
                                    reason=t['xfail']['reason'])]
                            else:
                                markers += [pytest.mark.xfail()]
                    if markers:
                        tests += [pytest.param(t, marks=markers,
                                               id=t['command'])]
                    else:
                        tests += [pytest.param(t, id=t['command'])]
    return tests


# pylint: disable=unused-argument
def setup_sqcmds(testvar, context_config):
    '''Setup the cli commands for testing'''

    sqcmd_path = [sys.executable, suzieq_cli_path]

    if 'data-directory' in testvar:
        # We need to create a tempfile to hold the config
        cfgfile = create_dummy_config_file(datadir=testvar['data-directory'])
        sqcmd_path += ['--config={}'.format(cfgfile)]

    exec_cmd = sqcmd_path + shlex.split(testvar['command'])

    output = None
    error = None
    try:
        output = check_output(exec_cmd)
    except CalledProcessError as e:
        error = e.output

    if cfgfile:
        os.remove(cfgfile)

    return output, error


def validate_host_shape(df: pd.DataFrame, ns_dict: dict):
    '''For the given DF, validate that the number of hosts is accurate'''
    for ns in ns_dict:
        if ns in df.namespace.unique():
            assert df.query(
                f'namespace == "{ns}"').hostname.nunique() == ns_dict[ns]
