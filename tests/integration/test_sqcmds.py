import os
import sys
import yaml
import json
from subprocess import check_output, CalledProcessError
import shlex
from tempfile import mkstemp
from collections import Counter

import pytest
from _pytest.mark.structures import Mark, MarkDecorator
from suzieq.cli.sqcmds import *

from nubia import context

from tests.conftest import commands, suzieq_cli_path

basic_verbs = ['show', 'summarize']


# TODO
# columns length, column names?
#  specific data?
@pytest.mark.slow
@pytest.mark.parametrize("command, verbs, args", [
    ('AddressCmd', basic_verbs, [None, None]),
    ('EvpnVniCmd', basic_verbs + ['aver'], [None, None, None]),
    ('InterfaceCmd', basic_verbs + ['top', 'aver'],
     [None, None, None]),
    ('LldpCmd', basic_verbs, [None, None]),
    ('MacCmd', basic_verbs, [None, None]),
    ('MlagCmd', basic_verbs, [None, None, None]),
    ('OspfCmd', basic_verbs + ['aver'], [None, None, None, None]),
    ('RouteCmd', basic_verbs + ['lpm'],
     [None, None, {'address': '10.0.0.1'}]),
    ('TableCmd', ['show', 'describe'], [None, {'table': 'device'}]),
    #    ('TopcpuCmd', basic_verbs, [None, None]),
    #    ('TopmemCmd', basic_verbs, [None, None]),
    ('VlanCmd', basic_verbs, [None, None])
])
def test_commands(setup_nubia, command, verbs, args):
    """ runs through all of the commands for each of the sqcmds
    command: one of the sqcmds
    verbs: for each command, the list of verbs
    args: arguments
    """
    for v, arg in zip(verbs, args):
        _test_command(command, v, arg)


def _test_command(cmd, verb, arg, filter=None):

    s = execute_cmd(cmd, verb, arg, filter)
    assert isinstance(s, int)
    return s


def test_summary_exception(setup_nubia):
    s = None
    with pytest.raises(AttributeError):
        s = execute_cmd('DeviceCmd', 'foop', None, )
    assert s is None


good_commands = commands[:]

column_commands = good_commands[:]


@pytest.mark.parametrize("cmd", column_commands)
def test_all_columns(setup_nubia, cmd):
    s = _test_command(cmd, 'show', None, filter={'columns': '*'})
    assert s == 0


@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_hostname_show_filter(setup_nubia, cmd):
    s = _test_command(cmd, 'show', None, {'hostname': 'leaf01'})
    assert s == 0


@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_engine_show_filter(setup_nubia, cmd):
    s = _test_command(cmd, 'show', None, {'engine': 'pandas'})
    assert s == 0


@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_namespace_show_filter(setup_nubia, cmd):
    s = _test_command(cmd, 'show', None, {'namespace': 'dual-bgp'})
    assert s == 0


@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_view_show_filter(setup_nubia, cmd):
    s = _test_command(cmd, 'show', None, {'view': 'all'})
    assert s == 0


@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_start_time_show_filter(setup_nubia, cmd):
    s = _test_command(cmd, 'show', None, {
                      'start_time': '2020-01-01 21:43:30.048'})
    assert s == 0


show_columns_commands = good_commands[:]


@pytest.mark.filter
@pytest.mark.fast
@pytest.mark.parametrize("cmd", show_columns_commands)
def test_columns_show_filter(setup_nubia, cmd):
    s = _test_command(cmd, 'show', None, {'columns': 'hostname'})
    assert s == 0


bad_hostname_commands = commands[:]


@pytest.mark.filter
@pytest.mark.parametrize("cmd", bad_hostname_commands)
def test_bad_show_hostname_filter(setup_nubia, cmd):
    filter = {'hostname': 'unknown'}
    _ = _test_bad_show_filter(cmd, filter)


bad_engine_commands = commands[:]
bad_engine_commands.pop(4)  # EvpnVniCmd
bad_engine_commands.pop(8)  # Ospfcmd


@pytest.mark.filter
@pytest.mark.parametrize("cmd", bad_engine_commands)
def test_bad_show_engine_filter(setup_nubia, cmd):
    filter = {'engine': 'unknown'}
    _ = _test_bad_show_filter(cmd, filter)


bad_start_time_commands = commands[:]


# TODO

# this is the placeholder of the nubia bug about parsing 'start-time'
@pytest.mark.filter
@pytest.mark.xfail(reason='bug #12', raises=TypeError)
@pytest.mark.parametrize("cmd", bad_start_time_commands)
def test_show_start_time_filter(setup_nubia, cmd):
    filter = {'start-time': 'unknown'}
    _ = _test_bad_show_filter(cmd, filter)


# this because I need to xfail these for this bug, I can't xfail individual
# ones for the filenotfound
# so I must remove those from the stack
bad_start_time_commands.pop(3)  # EvpnVniCmd
bad_start_time_commands.pop(7)  # Ospfcmd


@pytest.mark.filter
@pytest.mark.parametrize("cmd", bad_start_time_commands)
def test_bad_start_time_filter(setup_nubia, cmd):
    filter = {'start_time': 'unknown'}
    _ = _test_bad_show_filter(cmd, filter)


bad_namespace_commands = bad_hostname_commands[:]


# TODO
# this is just like hostname filtering
@pytest.mark.filter
@pytest.mark.parametrize("cmd", bad_namespace_commands)
def test_bad_show_namespace_filter(setup_nubia, cmd):
    filter = {'namespace': 'unknown'}
    _ = _test_bad_show_filter(cmd, filter)


def _test_bad_show_filter(cmd, filter):
    assert len(filter) == 1
    s = _test_command(cmd, 'show', None, filter=filter)
    assert s == 0
    return s


good_filters = [{'hostname': 'leaf01'}]


# TODO?
#  these only check good cases, I'm assuming the bad cases work the same
#  as the rest of the filtering, and that is too messy to duplicate right now
@pytest.mark.filter
@pytest.mark.parametrize('cmd', good_commands)
def test_context_filtering(setup_nubia, cmd):
    for filter in good_filters:
        s = _test_context_filtering(cmd, filter)
        assert s == 0


context_namespace_commands = commands[:]


@pytest.mark.filter
@pytest.mark.parametrize('cmd', context_namespace_commands)
def test_context_namespace_filtering(setup_nubia, cmd):
    s = _test_context_filtering(cmd, {'namespace': ['dual-bgp']})
    # this has to be list or it will fail, different from any other filtering,
    # namespace is special because it's part of the directory structure
    assert s == 0


@pytest.mark.filter
@pytest.mark.parametrize('cmd', good_commands)
def test_context_engine_filtering(setup_nubia, cmd):
    s = _test_context_filtering(cmd, {'enginename': 'pandas'})
    assert s == 0


@pytest.mark.fast
@pytest.mark.parametrize('cmd', good_commands)
def test_context_start_time_filtering(setup_nubia, cmd):
    # before the latest data, so might be more data than the default
    s = _test_context_filtering(cmd, {'start_time': '2020-01-20 0:0:0'})
    assert s == 0


def _test_context_filtering(cmd, filter):
    assert len(filter) == 1
    ctx = context.get_context()
    k = next(iter(filter))
    v = filter[k]
    setattr(ctx, k, v)
    s = _test_command(cmd, 'show', None)
    assert s == 0
    setattr(ctx, k, "")  # reset ctx back to no filtering
    return s


def execute_cmd(cmd, verb, arg, filter=None):
    # expect the cmd class are in the module cmd and also named cmd
    module = globals()[cmd]
    instance = getattr(module, cmd)
    if filter is None:
        filter = {}
        #filter = {'format': 'dataframe'}
    # else:
    #    filter['format'] = 'dataframe'
    instance = instance(**filter)

    c = getattr(instance, verb)
    if arg is not None:
        return c(**arg)
    else:
        return c()


def _load_up_the_tests():
    "reads the files from the samples directory and parametrizes the test"
    tests = []
    for i in os.scandir(os.path.abspath(os.curdir) +
                        '/tests/integration/sqcmds/samples'):
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


@pytest.mark.smoke
@pytest.mark.sqcmds
@pytest.mark.parametrize("testvar", _load_up_the_tests())
def test_sqcmds(testvar, create_context_config):
    sqcmd_path = [sys.executable, suzieq_cli_path]
    tmpfname = None

    if 'data-directory' in testvar:
        # We need to create a tempfile to hold the config
        tmpconfig = create_context_config
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

    jout = []
    if output:
        try:
            jout = json.loads(output.decode('utf-8').strip())
        except json.JSONDecodeError:
            jout = output

    if 'output' in testvar:
        try:
            expected_jout = json.loads(testvar['output'].strip())
        except json.JSONDecodeError:
            expected_jout = testvar['output']

        assert (type(expected_jout) == type(jout))
        if isinstance(jout, dict):
            assert (Counter(expected_jout) == Counter(jout))
            return
        try:
            expected_setlist = set(tuple(sorted(d.items())) for d in jout)
            got_setlist = set(tuple(sorted(d.items())) for d in expected_jout)
            assert (expected_setlist == got_setlist)
        except TypeError:
            # This is for commands that return lists in their outputs.
            # This isn't robust, because it assumes that we get the output
            # back in sorted order except that the keys within each entry
            # are not sorted. If the outer sort is changed, this won't work
            expected = [sorted(d.items()) for d in expected_jout]
            got = [sorted(d.items()) for d in jout]
            assert (expected == got)

    elif error and 'xfail' in testvar and 'error' in testvar['xfail']:
        if jout.decode("utf-8") == testvar['xfail']['error']:
            assert False
        else:
            assert True
    elif error and 'error' in testvar and 'error' in testvar['error']:
        try:
            jerror = json.loads(error.decode('utf-8').strip())
        except json.JSONDecodeError:
            jerror = error.decode('utf-8').strip()
        jterror = json.loads(testvar['error']['error'])
        assert jerror == jterror
    else:
        raise Exception(f"either xfail or output requried {error}")
