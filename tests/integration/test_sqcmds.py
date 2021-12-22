import os
import json

import pytest
from _pytest.mark.structures import Mark, MarkDecorator

from tests.conftest import (commands, load_up_the_tests, tables, DATADIR,
                            setup_sqcmds, cli_commands,
                            create_dummy_config_file)
from suzieq.sqobjects import get_sqobject, get_tables
from suzieq.cli.sqcmds import *  # noqa

from nubia import context
import pandas as pd

from .utils import assert_df_equal

verbs = ['show', 'summarize', 'describe', 'help']


@pytest.mark.sqcmds
@pytest.mark.slow
@pytest.mark.parametrize("command",  [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
@pytest.mark.parametrize("verb", [
    pytest.param(verb, marks=MarkDecorator(Mark(verb, [], {})))
    for verb in verbs])
def test_commands(setup_nubia, get_cmd_object_dict, command, verb):
    """ runs through all of the commands for each of the sqcmds
    command: one of the sqcmds
    verbs: for each command, the list of verbs
    args: arguments
    """

    _test_command(get_cmd_object_dict[command], verb, None)


def _test_command(cmd, verb, arg, filter=None):

    if ((cmd == 'PathCmd') and (verb != "help") and
            (not filter or not all(x in filter for x in ['src', 'dest']))):
        if not filter:
            filter = {}
        filter.update({'namespace': 'dual-bgp',
                       'src': '10.0.0.11',
                       'dest': '10.0.0.14'})
    s = execute_cmd(cmd, verb, arg, filter)
    assert isinstance(s, int)
    return s

@pytest.mark.sqcmds
def test_summary_exception(setup_nubia):
    s = None
    with pytest.raises(AttributeError):
        s = execute_cmd('DeviceCmd', 'foop', None, )
    assert s is None


@pytest.mark.sqcmds
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_all_columns(setup_nubia, get_cmd_object_dict, cmd):
    s = _test_command(get_cmd_object_dict[cmd], 'show', None,
                      filter={'columns': '*'})
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_hostname_show_filter(setup_nubia, get_cmd_object_dict, cmd):
    if cmd != "table":
        s = _test_command(get_cmd_object_dict[cmd], 'show', None,
                          {'hostname': 'leaf01'})
        assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_engine_show_filter(setup_nubia, get_cmd_object_dict, cmd):
    s = _test_command(get_cmd_object_dict[cmd], 'show', None,
                      {'engine': 'pandas'})
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_namespace_show_filter(setup_nubia, get_cmd_object_dict, cmd):
    s = _test_command(get_cmd_object_dict[cmd], 'show', None,
                      {'namespace': 'dual-bgp'})
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_view_show_filter(setup_nubia, get_cmd_object_dict, cmd):
    s = _test_command(get_cmd_object_dict[cmd], 'show', None, {'view': 'all'})
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_start_time_show_filter(setup_nubia, get_cmd_object_dict, cmd):
    s = _test_command(get_cmd_object_dict[cmd], 'show', None, {
                      'start_time': '2020-01-01 21:43:30.048'})
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.fast
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_columns_show_filter(setup_nubia, get_cmd_object_dict, cmd):
    if cmd != "table":
        s = _test_command(get_cmd_object_dict[cmd], 'show', None,
                          {'columns': 'namespace'})
        assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_bad_show_hostname_filter(setup_nubia, get_cmd_object_dict, cmd):
    filter = {'hostname': 'unknown'}
    _ = _test_bad_show_filter(get_cmd_object_dict[cmd], filter)


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_bad_show_engine_filter(setup_nubia, get_cmd_object_dict, cmd):
    filter = {'engine': 'unknown'}
    _ = _test_bad_show_filter_w_assert(get_cmd_object_dict[cmd], filter)


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_bad_start_time_filter(setup_nubia, get_cmd_object_dict, cmd):
    filter = {'start_time': 'unknown'}
    _ = _test_bad_show_filter(get_cmd_object_dict[cmd], filter, True)


# TODO
# this is just like hostname filtering
@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize("cmd", [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_bad_show_namespace_filter(setup_nubia, get_cmd_object_dict, cmd):
    filter = {'namespace': 'unknown'}
    _ = _test_bad_show_filter(get_cmd_object_dict[cmd], filter)


def _test_bad_show_filter(cmd, filter, assert_error=False):
    assert len(filter) == 1
    s = _test_command(cmd, 'show', None, filter=filter)
    if assert_error:
        assert s == 1
    else:
        assert s == 0
    return s


def _test_bad_show_filter_w_assert(cmd, filter):
    assert len(filter) == 1
    try:
        _test_command(cmd, 'show', None, filter=filter)
        assert False
    except ModuleNotFoundError:
        assert True
    return 0


good_filters = [{'hostname': ['leaf01']}]


# TODO?
#  these only check good cases, I'm assuming the bad cases work the same
#  as the rest of the filtering, and that is too messy to duplicate right now
@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize('cmd', [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_context_filtering(setup_nubia, get_cmd_object_dict, cmd):
    for filter in good_filters:
        s = _test_context_filtering(get_cmd_object_dict[cmd], filter)
        assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize('cmd', [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_context_namespace_filtering(setup_nubia, get_cmd_object_dict, cmd):
    s = _test_context_filtering(get_cmd_object_dict[cmd],
                                {'namespace': ['dual-bgp']})
    # this has to be list or it will fail, different from any other filtering,
    # namespace is special because it's part of the directory structure
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.filter
@pytest.mark.parametrize('cmd', [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_context_engine_filtering(setup_nubia, get_cmd_object_dict, cmd):
    s = _test_context_filtering(get_cmd_object_dict[cmd], {'engine': 'pandas'})
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.fast
@pytest.mark.parametrize('cmd', [
    pytest.param(cmd, marks=MarkDecorator(Mark(cmd, [], {})))
    for cmd in cli_commands])
def test_context_start_time_filtering(setup_nubia, get_cmd_object_dict, cmd):
    # before the latest data, so might be more data than the default
    s = _test_context_filtering(get_cmd_object_dict[cmd],
                                {'start_time': '2020-01-20 0:0:0'})
    assert s == 0


@pytest.mark.sqcmds
@pytest.mark.parametrize('table', tables)
def test_table_describe(setup_nubia, table):
    out = _test_command('TableCmd', 'describe', {"table": table})
    assert out == 0


@pytest.mark.sqcmds
@ pytest.mark.parametrize('table',
                          [pytest.param(
                              x,
                              marks=MarkDecorator(Mark(x, [], {})))
                           for x in get_tables()
                           if x not in ['path', 'topmem', 'topcpu',
                                        'topmem', 'time', 'ifCounters',
                                        'ospfIf', 'ospfNbr',
                                        'network', 'inventory']
                           ])
@ pytest.mark.parametrize('datadir', DATADIR)
def test_sqcmds_regex_hostname(table, datadir):

    cfgfile = create_dummy_config_file(datadir=datadir)

    df = get_sqobject(table)(config_file=cfgfile).get(
        hostname=['~leaf.*', '~exit.*'])

    if table == 'tables':
        if 'junos' in datadir:
            assert df[df.table == 'device']['deviceCnt'].tolist() == [4]
        elif not any(x in datadir for x in ['vmx', 'mixed']):
            # The hostnames for these output don't match the hostname regex
            assert df[df.table == 'device']['deviceCnt'].tolist() == [6]
        return
    if 'basic_dual_bgp' in datadir and table in ['ospf', 'evpnVni', 'devconfig']:
        return

    if not any(x in datadir for x in ['vmx', 'mixed', 'junos']):
        assert not df.empty

        if table in ['macs', 'vlan'] and 'basic_dual_bgp' in datadir:
            assert set(df.hostname.unique()) == set(['leaf01', 'leaf02',
                                                     'leaf03', 'leaf04'])
        elif table not in ['mlag']:
            assert set(df.hostname.unique()) == set(['leaf01', 'leaf02',
                                                     'leaf03', 'leaf04',
                                                     'exit01', 'exit02'])

        else:
            assert set(df.hostname.unique()) == set(['leaf01', 'leaf02',
                                                     'leaf03', 'leaf04'])
    elif 'junos' in datadir:
        if table == 'mlag':
            # Our current Junos tests don't have MLAG
            return
        assert not df.empty
        if table == 'macs':
            assert set(df.hostname.unique()) == set(['leaf01', 'leaf02'])
        else:
            assert set(df.hostname.unique()) == set(['leaf01', 'leaf02',
                                                     'exit01', 'exit02'])


@pytest.mark.sqcmds
@ pytest.mark.parametrize('table',
                          [pytest.param(
                              x,
                              marks=MarkDecorator(Mark(x, [], {})))
                           for x in get_tables()
                           if x not in ['path', 'inventory']
                           ])
@ pytest.mark.parametrize('datadir', ['tests/data/multidc/parquet-out/'])
def test_sqcmds_regex_namespace(table, datadir):

    cfgfile = create_dummy_config_file(datadir=datadir)

    df = get_sqobject(table)(config_file=cfgfile).get(
        hostname=['~leaf.*', '~exit.*'], namespace=['~ospf.*'])

    assert not df.empty
    if table == 'tables':
        assert df[df.table == 'device']['namespaces'].tolist() == [2]
        return

    if table in ['mlag', 'evpnVni', 'devconfig', 'bgp']:
        # why devconfig is empty for ospf-single needs investigation
        assert set(df.namespace.unique()) == set(['ospf-ibgp'])
    else:
        assert set(df.namespace.unique()) == set(['ospf-ibgp', 'ospf-single'])

    if table in ['network']:
        # network show has no hostname
        return

    if table not in ['mlag']:
        assert set(df.hostname.unique()) == set(['leaf01', 'leaf02',
                                                 'leaf03', 'leaf04',
                                                 'exit01', 'exit02'])
    else:
        assert set(df.hostname.unique()) == set(['leaf01', 'leaf02',
                                                 'leaf03', 'leaf04'])


def _test_context_filtering(cmd, filter):
    assert len(filter) == 1
    ctx = context.get_context()
    k = next(iter(filter))
    v = filter[k]
    setattr(ctx, k, v)
    s = _test_command(cmd, 'show', None)
    setattr(ctx, k, "")  # reset ctx back to no filtering
    return s


def execute_cmd(cmd, verb, arg, filter=None):
    # expect the cmd class are in the module cmd and also named cmd
    module = globals()[cmd]
    instance = getattr(module, cmd)
    if filter is None:
        filter = {}
        # filter = {'format': 'dataframe'}
    # else:
    #    filter['format'] = 'dataframe'
    instance = instance(**filter)

    c = getattr(instance, verb)
    if arg is not None:
        return c(**arg)
    else:
        return c()


def _test_sqcmds(testvar, context_config):
    output, error = setup_sqcmds(testvar, context_config)

    if output:
        try:
            jout = json.loads(output.decode('utf-8').strip())
        except json.JSONDecodeError:
            jout = output

    if 'ignore-columns' in testvar:
        ignore_cols = testvar['ignore-columns'].split()
    else:
        ignore_cols = []

    if 'output' in testvar:
        if testvar.get('format', '') == "text":
            assert output.decode('utf8') == testvar['output']
            return

        # pandas uses ujson and needs to escape "/" in any string its trying
        # to decode. This is true in the case of NXOS' LLDP description which
        # contains a URL causing read_json to abort with weird error messages.
        expected_df = pd.read_json(
            testvar['output'].strip().replace('/', r'\/'))

        try:
            got_df = pd.read_json(output.decode('utf8').strip())
        except AttributeError:
            if output:
                got_df = pd.read_json(output)
            else:
                got_df = pd.DataFrame()

        # expected_df.sort_values(by=expected_df.columns[:1].tolist()) \
        #            .reset_index(drop=True)
        # got_df = got_df.sort_values(by=got_df.columns[:1].tolist()) \
        #                .reset_index(drop=True)
        # assert(expected_df.shape == got_df.shape)
        assert_df_equal(expected_df, got_df, ignore_cols)

    elif not error and 'xfail' in testvar:
        # this was marked to fail, but it succeeded so we must return
        return
    elif error and 'xfail' in testvar and 'error' in testvar['xfail']:
        if jout.decode("utf-8") == testvar['xfail']['error']:
            assert False
        else:
            assert True
    elif error and 'error' in testvar and 'error' in testvar['error']:
        try:
            got_df = pd.DataFrame(json.loads(error.decode('utf-8').strip()))
        except json.JSONDecodeError:
            got_df = pd.DataFrame({'error': [error.decode('utf-8').strip()]})

        expected_df = pd.DataFrame(json.loads(testvar['error']['error']))

        assert_df_equal(expected_df, got_df, ignore_cols)
    else:
        raise Exception(f"either xfail or output requried {error}")


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize(
    "testvar",
    load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                      '/tests/integration/sqcmds/cumulus-samples')))
def test_cumulus_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize(
    "testvar",
    load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                 '/tests/integration/sqcmds/nxos-samples')))
def test_nxos_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize(
    "testvar",
    load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                 '/tests/integration/sqcmds/junos-samples')))
def test_junos_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize(
    "testvar",
    load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                 '/tests/integration/sqcmds/eos-samples')))
def test_eos_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize(
    "testvar",
    load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                 '/tests/integration/sqcmds/mixed-samples')))
def test_mixed_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize(
    "testvar",
    load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                 '/tests/integration/sqcmds/vmx-samples')))
def test_vmx_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize(
    "testvar",
    load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                 '/tests/integration/sqcmds/common-samples')))
def test_common_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)
