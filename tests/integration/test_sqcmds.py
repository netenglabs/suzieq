import pytest

from pandas import DataFrame

from suzieq.cli.sqcmds import *
from pyarrow.lib import ArrowInvalid
from pandas.core.computation.ops import UndefinedVariableError
# TODO
# set and clear context
#
# only works if there is a suzieq-cfg.yml file, which it then over-rides
# how do I make sure I check all svcs and all commands

# I don't know the right measure of completeness to cover all the different ways of filtering


basic_cmds = ['show', 'summarize']


# TODO
# columns length, column names?
#  specific data?
@pytest.mark.slow
@pytest.mark.parametrize("svc, commands, args, size,", [
    ('addrCmd', basic_cmds, [None, None], [324, 18],),
    ('arpndCmd', basic_cmds, [None, None], [592, 48]),
    ('bgpCmd', basic_cmds, [None, None], [352, 143]),
    ('evpnVniCmd', basic_cmds, [None, None], [FileNotFoundError, FileNotFoundError]), # TODO: bug #16
    ('interfaceCmd', basic_cmds + ['top', 'aver'], [None, None, None, None], [1518, 143, 60, 0]),
    ('lldpCmd', basic_cmds, [None, None], [352, 48]),
    ('macsCmd', basic_cmds, [None, None], [312, 48]),
    ('mlagCmd', basic_cmds + ['describe'], [None, None, None], [44, NotImplementedError, 143]),
    ('ospfCmd', basic_cmds + ['top', 'aver'], [None, None, None, None],
     [FileNotFoundError, FileNotFoundError, FileNotFoundError, FileNotFoundError]),  # TODO: bug #16
    ('routesCmd', basic_cmds + ['lpm'], [None, None, {'address': '10.0.0.1'}], [2596, 66, 143]),
    ('systemCmd', basic_cmds, [None, None], [140, 130]),
    ('tablesCmd', basic_cmds, [None, {'table': 'system'}], [14, 22]),
    ('topcpuCmd', basic_cmds, [None, None], [42, 18]),
    ('topmemCmd', basic_cmds, [None, None], [27, 18]),
    ('vlanCmd', basic_cmds, [None, None], [96, 78])
])
def test_commands(setup_nubia, svc, commands, args, size):
    """ runs through all of the commands for each of the sqcmds
    svc: a service
    commands: for each service, the list of commands
    args: arguments
    size: for each command, expected size of returned data, or Exception of the command is invalid"""
    for cmd, arg, sz in zip(commands, args, size):
        _test_command(svc, cmd, arg, sz)


def _test_command(svc, cmd, arg, sz, filter=None):
    s = None
    if isinstance(sz, type) and isinstance(sz(), Exception):
        with pytest.raises(sz):
            execute_cmd(svc, cmd, arg, filter)

    else:
        s = execute_cmd(svc, cmd, arg, filter)
        assert isinstance(s, DataFrame)
        if sz is not None:
            assert s.size == sz
    return s


def test_summary_exception(setup_nubia):
    s = None
    with pytest.raises(AttributeError):
        s = execute_cmd('systemCmd', 'foop', None, )
    assert s is None

svcs = [
    ('addrCmd'),
    ('arpndCmd'),
    ('bgpCmd'),
    ('evpnVniCmd'),
    ('interfaceCmd'),
    ('lldpCmd'),
    ('macsCmd'),
    ('mlagCmd'),
    ('ospfCmd'),
    ('routesCmd'),
    ('systemCmd'),
    ('topcpuCmd'),
    ('topmemCmd'),
    ('vlanCmd')]

# these fail for every command because they are missing data
svcs[3] = pytest.param(svcs[3], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError)) # evpnVniCmd
svcs[8] = pytest.param(svcs[8], marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError)) # ospfCmd

good_svcs = svcs[:]

# TODO: these break things
# [{'columns': 'hostname'}, {'start_time': ??}]
basic_filters = [{'hostname': 'leaf01'}, {'engine': 'pandas'}, {'datacenter': 'dual-bgp'}]


@pytest.mark.filter
@pytest.mark.parametrize("svc", good_svcs)
def test_show_filter(setup_nubia, svc):
    for filter in basic_filters:
        assert len(filter) == 1
        s1 = _test_command(svc, 'show', None, None)
        s = _test_command(svc, 'show', None, None, filter=filter)
        filter_key = next(iter(filter))
        if filter_key in s.columns:  # sometimes the filter isn't a part of the data returned
            assert len(s[filter_key].unique()) == 1
            assert s[filter_key][0] == filter[filter_key]
            assert len(s1[filter_key].unique()) >= len(s[filter_key].unique())
        assert s1.size >= s.size


bad_hostname_svcs = svcs[:]
bad_hostname_svcs[0] = pytest.param(svcs[0], marks=pytest.mark.xfail(reason='bug #15', raises=ArrowInvalid))  # addrCmd
bad_hostname_svcs[6] = pytest.param(svcs[6], marks=pytest.mark.xfail(reason='bug #15', raises=ArrowInvalid))  # macsCmd
bad_hostname_svcs[9] = pytest.param(svcs[9], marks=pytest.mark.xfail(reason='bug #14', raises=UndefinedVariableError)) # routesCmd
bad_hostname_svcs[10] = pytest.param(svcs[10], marks=pytest.mark.xfail(reason='bug #7', raises=KeyError))  # systemCmd
bad_hostname_svcs[13] = pytest.param(svcs[13], marks=pytest.mark.xfail(reason='bug #15', raises=ArrowInvalid))  # vlan
@pytest.mark.filter
@pytest.mark.parametrize("svc", bad_hostname_svcs)
def test_bad_show_hostname_filter(setup_nubia, svc):
    filter = {'hostname': 'unknown'}
    s = _test_bad_show_filter(svc, filter)


bad_engine_svcs = svcs[:]
# TODO
# this doesn't do any filtering, so it fails the assert that length should be 0
# when this is fixed then remove the xfail
@pytest.mark.filter
@pytest.mark.xfail(reason='bug #11') #
@pytest.mark.parametrize("svc", bad_engine_svcs)
def test_bad_show_engine_filter(setup_nubia, svc):
    filter = {'engine': 'unknown'}
    s = _test_bad_show_filter(svc, filter)


bad_start_time_svcs = svcs[:]
# TODO
# this doesn't do any filtering, so it fails the assert that length should be 0
# when this is fixed then remove the xfail
@pytest.mark.filter
@pytest.mark.xfail(reason='bug #12')
@pytest.mark.parametrize("svc", bad_start_time_svcs)
def test_bad_show_start_time_filter(setup_nubia, svc):
    filter = {'start_time': 'unknown'}
    s = _test_bad_show_filter(svc, filter)


bad_datacenter_svcs = bad_hostname_svcs[:]
# TODO
# this is just like hostname filtering
@pytest.mark.filter
@pytest.mark.parametrize("svc", bad_datacenter_svcs)
def test_bad_show_datacenter_filter(setup_nubia, svc):
    filter = {'datacenter': 'unknown'}
    s = _test_bad_show_filter(svc, filter)


def _test_bad_show_filter(svc, filter):
    assert len(filter) == 1
    s = _test_command(svc, 'show', None, None, filter=filter)
    assert len(s) == 0
    return s


def execute_cmd(svc, cmd, arg, filter=None):
    # expect the svc class are in the module svc and also named svc
    module = globals()[svc]
    instance = getattr(module, svc)
    if filter is not None:
        instance = instance(**filter)
    else:
        instance = instance()

    c = getattr(instance, cmd)
    if arg is not None:
        return c(**arg)
    else:
        return c()


