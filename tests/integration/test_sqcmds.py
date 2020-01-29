import pytest

from pandas import DataFrame

from suzieq.cli.sqcmds import *
from pyarrow.lib import ArrowInvalid
from pandas.core.computation.ops import UndefinedVariableError
# TODO
# set and clear context
# test parameters filtering

# is it possible to split the commands as different tests, rather than just the services?
# only works if there is a suzieq-cfg.yml file, which it then over-rides
# how do I make sure I check all svcs and all commands

# I don't know the right measure of completeness to cover all the different ways of filtering


basic_cmds = ['show', 'summarize']


# TODO
# columns length, column names?
#  specific data?
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


@pytest.mark.slow
@pytest.mark.filter
def test_hostname_filter(setup_nubia):
    s1 = _test_command('systemCmd', 'show', None, 140)
    s1_len = len(s1['hostname'])
    s = _test_command('systemCmd', 'show', None, 140/s1_len, filter={'hostname': 'leaf01'})
    assert len(s['hostname']) == 1
    assert s['hostname'][0] == 'leaf01'


working_svcs = [
    ('addrCmd'),
    ('arpndCmd'),
    ('bgpCmd'),
    pytest.param(('evpnVniCmd'), marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError)),
    ('interfaceCmd'),
    ('lldpCmd'),
    ('macsCmd'),
    ('mlagCmd'),
    pytest.param(('ospfCmd'), marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError)),
    ('routesCmd'),
    ('systemCmd'),
    ('topcpuCmd'),
    ('topmemCmd'),
    ('vlanCmd')]
basic_filters = [{'hostname': 'leaf01'}]
bad_filters = [{'hostname': 'leaf'}]
# can only include commands that have data here because we aren't passing Exceptions
@pytest.mark.slow
@pytest.mark.filter
@pytest.mark.parametrize("svc", working_svcs)
def test_show_filter(setup_nubia, svc):
    for filter in basic_filters:
        assert len(filter) == 1
        s1 = _test_command(svc, 'show', None, None)
        s1_size = s1['hostname'].unique().size
        s = _test_command(svc, 'show', None, None, filter=filter)
        filter_key = next(iter(filter))
        assert len(s[filter_key].unique()) == 1
        assert s[filter_key][0] == filter[filter_key]
        assert len(s1[filter_key].unique()) > len(s[filter_key].unique())

working_svcs = [
    pytest.param(('addrCmd'), marks=pytest.mark.xfail(reason='bug #15', raises=ArrowInvalid)),
    ('arpndCmd'),
    ('bgpCmd'),
    pytest.param(('evpnVniCmd'), marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError)),
    ('interfaceCmd'),
    ('lldpCmd'),
    pytest.param(('macsCmd'), marks=pytest.mark.xfail(reason='bug #15', raises=ArrowInvalid)),
    ('mlagCmd'),
    pytest.param(('ospfCmd'), marks=pytest.mark.xfail(reason='bug #16', raises=FileNotFoundError)),
    pytest.param(('routesCmd'), marks=pytest.mark.xfail(reason='bug #14', raises=UndefinedVariableError)),
    pytest.param(('systemCmd'), marks=pytest.mark.xfail(reason='bug #7', raises=KeyError)),
    ('topcpuCmd'),
    ('topmemCmd'),
    pytest.param(('vlanCmd'), marks=pytest.mark.xfail(reason='bug #15' , raises=ArrowInvalid))
]
@pytest.mark.slow
@pytest.mark.filter
@pytest.mark.parametrize("svc", working_svcs)
def test_bad_show_filter(setup_nubia, svc):
    for filter in bad_filters:
        assert len(filter) == 1
        s = _test_command(svc, 'show', None, None, filter=filter)
        assert s.size == 0


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


