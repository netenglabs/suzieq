import pytest

from pandas import DataFrame
from nubia import context

from suzieq.cli.sqcmds import *
from pyarrow.lib import ArrowInvalid
from pandas.core.computation.ops import UndefinedVariableError

from tests.conftest import commands
# TODO
# after time filtering if fixed, figure out more subtle time testing
# test more than just show for filtering?
#
# only works if there is a suzieq-cfg.yml file, which it then over-rides
# how do I make sure I check all commands and all verbs

# I don't know the right measure of completeness to cover all the different ways of filtering
# missing detailed checking of whatever is being done directly in the sqcmds objects, such as filtering or formatting changes


basic_verbs = ['show', 'summarize']


# TODO
# columns length, column names?
#  specific data?
@pytest.mark.slow
@pytest.mark.parametrize("command, verbs, args, size,", [
    ('AddrCmd', basic_verbs, [None, None], [324, 18],),
    ('ArpndCmd', basic_verbs, [None, None], [592, 48]),
    ('BgpCmd', basic_verbs, [None, None], [352, 143]),
    ('EvpnVniCmd', basic_verbs, [None, None], [FileNotFoundError, FileNotFoundError]), # TODO: bug #16
    ('InterfaceCmd', basic_verbs + ['top', 'aver'], [None, None, None, None], [1518, 143, 60, 0]),
    ('LldpCmd', basic_verbs, [None, None], [352, 48]),
    ('MacsCmd', basic_verbs, [None, None], [312, 48]),
    ('MlagCmd', basic_verbs + ['describe'], [None, None, None], [44, NotImplementedError, 143]),
    ('OspfCmd', basic_verbs + ['top', 'aver'], [None, None, None, None],
     [FileNotFoundError, FileNotFoundError, FileNotFoundError, FileNotFoundError]),  # TODO: bug #16
    ('RoutesCmd', basic_verbs + ['lpm'], [None, None, {'address': '10.0.0.1'}], [2596, 66, 65]),  # TODO: bug #24
    ('SystemCmd', basic_verbs, [None, None], [140, 130]),
    ('TablesCmd', basic_verbs, [None, {'table': 'system'}], [14, 22]),
    ('TopcpuCmd', basic_verbs, [None, None], [42, 18]),
    ('TopmemCmd', basic_verbs, [None, None], [27, 18]),
    ('VlanCmd', basic_verbs, [None, None], [96, 78])
])
def test_commands(setup_nubia, command, verbs, args, size):
    """ runs through all of the commands for each of the sqcmds
    command: one of the sqcmds
    verbs: for each command, the list of verbs
    args: arguments
    size: for each command, expected size of returned data, or Exception if the command is invalid"""
    for v, arg, sz in zip(verbs, args, size):
        _test_command(command, v, arg, sz)


def _test_command(cmd, verb, arg, sz, filter=None):
    s = None
    if isinstance(sz, type) and isinstance(sz(), Exception):
        with pytest.raises(sz):
            execute_cmd(cmd, verb, arg, filter)

    else:
        s = execute_cmd(cmd, verb, arg, filter)
        assert isinstance(s, DataFrame)
        if sz is not None:
            assert s.size == sz
    return s


def test_summary_exception(setup_nubia):
    s = None
    with pytest.raises(AttributeError):
        s = execute_cmd('SystemCmd', 'foop', None, )
    assert s is None

# these fail for every command because no data exists for these services
commands[3] = pytest.param(commands[3], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # evpnVniCmd
commands[8] = pytest.param(commands[8], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError))  # ospfCmd

good_commands = commands[:]

@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_hostname_show_filter(setup_nubia, cmd):
    s1, s2 = _test_good_show_filter(cmd, {'hostname': 'leaf01'})
    assert s1.size > s2.size

@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_engine_show_filter(setup_nubia, cmd):
    s1, s2 = _test_good_show_filter(cmd, {'engine': 'pandas'})
    assert s1.size == s2.size

@pytest.mark.filter
@pytest.mark.parametrize("cmd", good_commands)
def test_datacenter_show_filter(setup_nubia, cmd):
    s1, s2 = _test_good_show_filter(cmd, {'datacenter': 'dual-bgp'})
    assert s1.size == s2.size

@pytest.mark.filter
@pytest.mark.xfail(reason='bug #29')
@pytest.mark.parametrize("cmd", good_commands)
def test_view_show_filter(setup_nubia, cmd):
    s1, s2 = _test_good_show_filter(cmd, {'view': 'all'})
    assert s1.size < s2.size

@pytest.mark.filter
@pytest.mark.xfail(reason='bug #30')
@pytest.mark.parametrize("cmd", good_commands)
def test_start_time_show_filter(setup_nubia, cmd):
    s1, s2 = _test_good_show_filter(cmd, {'start_time': '2020-01-01 21:43:30.048'})
    assert s1 < s2  # should include more data because it includes a greater timeframe
    assert s1.equals(s2)

columns_commands = good_commands[:]
columns_commands[11] = pytest.param(columns_commands[11], marks=pytest.mark.xfail(reason="these commands aren't useful yet"))  # topCPU
columns_commands[12] = pytest.param(columns_commands[12], marks=pytest.mark.xfail(reason="these commands aren't useful yet"))  # topMem

@pytest.mark.filter
@pytest.mark.fast
@pytest.mark.parametrize("cmd", columns_commands)
def test_columns_show_filter(setup_nubia, cmd):
    s1, s2 = _test_good_show_filter(cmd, {'columns': 'hostname'})
    assert s1.size > s2.size

def _test_good_show_filter(cmd, filter):
    assert len(filter) == 1
    s1 = _test_command(cmd, 'show', None, None)
    s2 = _test_command(cmd, 'show', None, None, filter=filter)
    filter_key = next(iter(filter))
    if filter_key in s2.columns:  # sometimes the filter isn't a part of the data returned
        assert len(s2[filter_key].unique()) == 1
        assert s2[filter_key][0] == filter[filter_key]
        assert len(s1[filter_key].unique()) >= len(s2[filter_key].unique())
    assert s1.size >= s2.size
    return s1, s2


bad_hostname_commands = commands[:]
@pytest.mark.filter
@pytest.mark.parametrize("cmd", bad_hostname_commands)
def test_bad_show_hostname_filter(setup_nubia, cmd):
    filter = {'hostname': 'unknown'}
    s = _test_bad_show_filter(cmd, filter)


bad_engine_commands = commands[:]
# TODO
# this doesn't do any filtering, so it fails the assert that length should be 0
# when this is fixed then remove the xfail
@pytest.mark.filter
@pytest.mark.xfail(reason='bug #11')
@pytest.mark.parametrize("cmd", bad_engine_commands)
def test_bad_show_engine_filter(setup_nubia, cmd):
    filter = {'engine': 'unknown'}
    s = _test_bad_show_filter(cmd, filter)


bad_start_time_commands = commands[:]
# TODO
# this doesn't do any filtering, so it fails the assert that length should be 0
# when this is fixed then remove the xfail
@pytest.mark.filter
@pytest.mark.xfail(reason='bug #12')
@pytest.mark.parametrize("cmd", bad_start_time_commands)
def test_bad_show_start_time_filter(setup_nubia, cmd):
    filter = {'start_time': 'unknown'}
    s = _test_bad_show_filter(cmd, filter)


bad_datacenter_commands = bad_hostname_commands[:]


# TODO
# this is just like hostname filtering
@pytest.mark.filter
@pytest.mark.parametrize("cmd", bad_datacenter_commands)
def test_bad_show_datacenter_filter(setup_nubia, cmd):
    filter = {'datacenter': 'unknown'}
    s = _test_bad_show_filter(cmd, filter)


def _test_bad_show_filter(cmd, filter):
    assert len(filter) == 1
    s = _test_command(cmd, 'show', None, None, filter=filter)
    assert len(s) == 0
    return s


good_filters = [{'hostname': 'leaf01'}]

# TODO?
#  these only check good cases, I'm assuming the bad cases work the same
#  as the rest of the filtering, and that is too messy to duplicate right now
@pytest.mark.filter
@pytest.mark.parametrize('cmd', good_commands)
def test_context_filtering(setup_nubia, cmd):
    for filter in good_filters:
        _test_context_filtering(cmd, filter)


context_datacenter_commands = commands[:]
# TODO
# this is a terrible thing, but I can't think of another way
# remove system because it works, so it can't be marked as xfail
context_datacenter_commands.pop(10)
@pytest.mark.filter
@pytest.mark.xfail(reason='bug #18')
@pytest.mark.parametrize('cmd', context_datacenter_commands)
def test_context_datacenter_filtering(setup_nubia, cmd):
    _test_context_filtering(cmd, {'datacenter': 'dual-bgp'})


@pytest.mark.filter
@pytest.mark.xfail(reason='bug #17')
@pytest.mark.parametrize('cmd', good_commands)
def test_context_engine_filtering(setup_nubia, cmd):
    _test_context_filtering(cmd, {'engine': 'pandas'})


@pytest.mark.xfail(reason='bug 20')
@pytest.mark.parametrize('cmd', good_commands)
def test_context_start_time_filtering(setup_nubia, cmd):
    s1 = _test_command(cmd, 'show', None, None)
    s2 = _test_context_filtering(cmd, {'start_time': 1570006401})  # before the data was created
    s2 = s2.reset_index(drop=True)
    assert not all(s1.eq(s2)) # they should be different


def _test_context_filtering(cmd, filter):
    assert len(filter) == 1

    s1 = _test_command(cmd, 'show', None, None)
    assert len(s1) > 0
    ctx = context.get_context()

    k = next(iter(filter))
    v = filter[k]
    print(k, v)
    setattr(ctx, k, v)
    s2 = _test_command(cmd, 'show', None, None)
    assert len(s2) > 0  # these should be good filters, so some data should be returned
    assert len(s1) >= len(s2)
    setattr(ctx, k, "")  # reset ctx back to no filtering
    return s2


def execute_cmd(cmd, verb, arg, filter=None):
    # expect the cmd class are in the module cmd and also named cmd
    module = globals()[cmd]
    instance = getattr(module, cmd)
    if filter is not None:
        instance = instance(**filter)
    else:
        instance = instance()

    c = getattr(instance, verb)
    if arg is not None:
        return c(**arg)
    else:
        return c()


