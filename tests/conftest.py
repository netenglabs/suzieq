import pytest
from _pytest.mark.structures import Mark, MarkDecorator

import os
import sys
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext
from suzieq.poller.services import init_services
from unittest.mock import Mock
import yaml
import json
import pandas as pd
from tempfile import mkstemp
import shlex
from subprocess import check_output, CalledProcessError


suzieq_cli_path = './suzieq/cli/suzieq-cli'


commands = [('AddressCmd'), ('ArpndCmd'), ('BgpCmd'), ('DeviceCmd'),
            ('EvpnVniCmd'), ('InterfaceCmd'), ('LldpCmd'), ('MacCmd'),
            ('MlagCmd'), ('OspfCmd'), ('RouteCmd'),
            ('VlanCmd')]

cli_commands = [('arpnd'), ('address'), ('bgp'), ('device'), ('evpnVni'),
                ('fs'), ('interface'), ('lldp'), ('mac'),
                ('mlag'), ('ospf'), ('path'), ('route'), ('sqpoller'),
                ('topology'),
                ('vlan')]


tables = [('arpnd'), ('bgp'), ('evpnVni'), ('device'), ('fs'), ('ifCounters'),
          ('interfaces'), ('lldp'), ('macs'), ('mlag'),
          ('ospfIf'), ('ospfNbr'), ('path'), ('routes'), ('time'),
          ('topcpu'), ('topmem'), ('topology'), ('vlan')]


@pytest.fixture(scope='function')
def setup_nubia():
    _setup_nubia()


def _setup_nubia():
    from suzieq.cli.sq_nubia_plugin import NubiaSuzieqPlugin
    from nubia import Nubia
    # monkey patching -- there might be a better way
    plugin = NubiaSuzieqPlugin()
    plugin.create_context = create_context

    # this is just so that context can be created
    shell = Nubia(name='test', plugin=plugin)


def create_context():
    config = _create_context_config()
    context = NubiaSuzieqContext()
    context.cfg = config
    return context


@pytest.fixture()
def create_context_config():
    return _create_context_config()


def _create_context_config():
    config = {'schema-directory': './config/schema',
              'service-directory': './config',
              'data-directory': './tests/data/basic_dual_bgp/parquet-out',
              'temp-directory': '/tmp/suzieq',
              'logging-level': 'WARNING',
              'test_set': 'basic_dual_bgp',  # an extra field for testing
              'API_KEY': '68986cfafc9d5a2dc15b20e3e9f289eda2c79f40',
              'analyzer': {'timezone': 'GMT'},
              }
    return config


@pytest.fixture
@pytest.mark.asyncio
def init_services_default(event_loop):
    configs = os.path.abspath(os.curdir) + '/config/'
    schema = configs + 'schema/'
    mock_queue = Mock()
    services = event_loop.run_until_complete(
        init_services(configs, schema, mock_queue, True))
    return services


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
    tmpfname = None
    if 'data-directory' in testvar:
        # We need to create a tempfile to hold the config
        tmpconfig = context_config
        tmpconfig['data-directory'] = testvar['data-directory']

        fd, tmpfname = mkstemp(suffix='yml')
        f = os.fdopen(fd, 'w')
        f.write(yaml.dump(tmpconfig))
        f.close()
        sqcmd_path += ['--config={}'.format(tmpfname)]

    exec_cmd = sqcmd_path + shlex.split(testvar['command'])

    output = None
    error = None
    try:
        output = check_output(exec_cmd)
    except CalledProcessError as e:
        error = e.output

    if tmpfname:
        os.remove(tmpfname)

    return output, error

