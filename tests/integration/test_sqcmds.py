import pytest
from suzieq.cli.sqcmds import *
from nubia import context
import os
from tests.conftest import commands, load_up_the_tests, tables
from tempfile import mkstemp
import json
from tests.conftest import setup_sqcmds
import pandas as pd


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


@pytest.mark.parametrize('table', tables)
def test_table_describe(setup_nubia, table):
    out = _test_command('TableCmd', 'describe', {"table": table})
    assert out == 0


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
        # filter = {'format': 'dataframe'}
    # else:
    #    filter['format'] = 'dataframe'
    instance = instance(**filter)

    c = getattr(instance, verb)
    if arg is not None:
        return c(**arg)
    else:
        return c()


def assert_df_equal(expected_df, got_df, ignore_cols) -> None:
    '''Compare the dataframes for equality'''

    if ((expected_df.empty and not got_df.empty) or
            (not expected_df.empty and got_df.empty)):
        assert(got_df.shape == expected_df.shape)
        # We assume the asssert failure prevents the code from continuing

    if (expected_df.empty and got_df.empty):
        return

    # Drop any columns to be ignored
    if ignore_cols:
        if not got_df.empty:
            got_df.drop(columns=ignore_cols, inplace=True, errors='ignore')
        if not expected_df.empty:
            expected_df.drop(columns=ignore_cols,
                             inplace=True, errors='ignore')

    try:
        expected_df.sort_values(by=expected_df.columns.tolist(),
                                inplace=True)
        got_df.sort_values(by=got_df.columns.tolist(), inplace=True)
    except Exception:
        pass

    try:
        rslt_df = expected_df.compare(got_df, keep_equal=True)
        if not rslt_df.empty:
            matches = True
            # If there are lists in the values, their order maybe causing
            # the failure. Pass if the problem is the order but they're
            # equal
            for row in rslt_df.itertuples():
                if isinstance(row._1, list) and isinstance(row._2, list):
                    if set(row._1) != set(row._2):
                        matches = False
                        break
                else:
                    matches = False
                    break
            if not matches:
                print(rslt_df)
                assert(rslt_df.empty)
    except ValueError:
        # This happens when the two dataframes don't have the same shape
        # such as what happens if the return is an error. So, compare fails
        # and we have to try a different technique
        try:
            rslt_df = pd.merge(got_df,
                               expected_df,
                               how='outer',
                               indicator=True)
            if not got_df.empty:
                assert(not rslt_df.empty and rslt_df.query(
                    '_merge != "both"').empty)
        except Exception:
            assert(got_df.shape == expected_df.shape)
            assert('Unable to compare' == '')


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
        expected_df = pd.read_json(testvar['output'].strip())

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
            got_df = pd.DataFrame(error.decode('utf-8').strip())

        expected_df = pd.DataFrame(json.loads(testvar['error']['error']))

        assert_df_equal(expected_df, got_df, ignore_cols)
    else:
        raise Exception(f"either xfail or output requried {error}")


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize("testvar", load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                                                  '/tests/integration/sqcmds/cumulus-samples')))
def test_cumulus_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize("testvar", load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                                                  '/tests/integration/sqcmds/nxos-samples')))
def test_nxos_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize("testvar", load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                                                  '/tests/integration/sqcmds/junos-samples')))
def test_junos_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)


@ pytest.mark.smoke
@ pytest.mark.sqcmds
@ pytest.mark.parametrize("testvar", load_up_the_tests(os.scandir(os.path.abspath(os.curdir) +
                                                                  '/tests/integration/sqcmds/eos-samples')))
def test_eos_sqcmds(testvar, create_context_config):
    _test_sqcmds(testvar, create_context_config)
