from typing import List
from filelock import FileLock
from subprocess import check_output, CalledProcessError
import shlex
from tempfile import mkstemp
import yaml
from unittest.mock import Mock
from suzieq.poller.services.service_manager import ServiceManager
from suzieq.shared.utils import load_sq_config
from suzieq.shared.schema import Schema
from suzieq.sqobjects import get_sqobject, get_tables
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext
import sys
import os
from _pytest.mark.structures import Mark, MarkDecorator
import pytest
import pandas as pd

suzieq_cli_path = './suzieq/cli/sq_cli.py'
suzieq_rest_server_path = './suzieq/restServer/sq_rest_server.py'

DATADIR = ['tests/data/multidc/parquet-out/',
           'tests/data/eos/parquet-out',
           'tests/data/nxos/parquet-out',
           'tests/data/junos/parquet-out',
           'tests/data/mixed/parquet-out',
           'tests/data/vmx/parquet-out']

commands = [('AddressCmd'), ('ArpndCmd'), ('BgpCmd'), ('DeviceCmd'),
            ('DevconfigCmd'), ('EvpnVniCmd'), ('InterfaceCmd'),
            ('InventoryCmd'), ('LldpCmd'),
            ('MacCmd'), ('MlagCmd'), ('NetworkCmd'), ('OspfCmd'),
            ('SqPollerCmd'), ('RouteCmd'), ('TopologyCmd'), ('VlanCmd')]

cli_commands = [('arpnd'), ('address'), ('bgp'), ('device'), ('devconfig'),
                ('evpnVni'), ('fs'), ('interface'), ('inventory'), ('lldp'),
                ('mac'), ('mlag'), ('network'), ('ospf'), ('path'), ('route'),
                ('sqPoller'), ('topology'), ('vlan')]


tables = get_tables()


@pytest.fixture(scope='function')
def setup_nubia():
    _setup_nubia()


@pytest.fixture()
def create_context_config(datadir: str =
                          './tests/data/basic_dual_bgp/parquet-out'):
    return


@pytest.fixture()
def get_table_data(table: str, datadir: str):
    '''Get all fields including sqvers and any suppress field for DB check'''
    if table in ['path', 'ospfIf', 'ospfNbr']:
        return pd.DataFrame()

    cfgfile = create_dummy_config_file(datadir=datadir)
    sqobj = get_sqobject(table)(config_file=cfgfile)
    cols = sqobj.schema.get_display_fields(['*'])

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
    if table in ['path', 'ospfIf', 'ospfNbr']:
        return pd.DataFrame()

    cfgfile = create_dummy_config_file(datadir=datadir)
    df = get_sqobject(table)(config_file=cfgfile).get(columns=columns)

    return df


@ pytest.fixture
@ pytest.mark.asyncio
def init_services_default(event_loop):
    configs = os.path.abspath(os.curdir) + '/suzieq/config/'
    schema = configs + 'schema/'
    mock_queue = Mock()
    service_manager = ServiceManager(None, configs, schema,
                                     mock_queue, 'forever')
    services = event_loop.run_until_complete(service_manager.init_services())
    return services


@ pytest.fixture
def run_sequential(tmpdir):
    """Uses a file lock to run tests using this fixture, sequentially

    """
    with FileLock('test.lock', timeout=15):
        yield()


def _setup_nubia():
    from suzieq.cli.sq_nubia_plugin import NubiaSuzieqPlugin
    from nubia import Nubia
    # monkey patching -- there might be a better way
    plugin = NubiaSuzieqPlugin()
    plugin.create_context = create_context

    # this is just so that context can be created
    _ = Nubia(name='test', plugin=plugin)


def create_context():
    config = load_sq_config(config_file=create_dummy_config_file())
    context = NubiaSuzieqContext()
    context.cfg = config
    context.schemas = Schema(config["schema-directory"])
    return context


def create_dummy_config_file(
        datadir: str = './tests/data/basic_dual_bgp/parquet-out'):
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


def load_up_the_tests(dir):
    """reads the files from the samples directory and parametrizes the test"""
    tests = []

    for i in dir:
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
                        markers = [MarkDecorator(Mark(x, [], {}))
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


def setup_sqcmds(testvar, context_config):
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
