import pytest

from pandas import DataFrame

from suzieq.cli.sqcmds import *
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext

# TODO
# set and clear context
# test parameters filtering

# is it possible to split the commands as different tests, rather than just the services?
# only works if there is a suzieq-cfg.yml file, which it then over-rides
# how do I make sure I check all svcs and all commands


basic_cmds = ['show', 'summarize']


# TODO
# columns length, column names?
#  specific data?
@pytest.mark.parametrize("svc, commands, args, size,", [
    ('addrCmd', basic_cmds, [None, None], [324, 18],),
    ('arpndCmd', basic_cmds, [None, None], [592, 48]),
    ('bgpCmd', basic_cmds, [None, None], [352, 143]),
    ('evpnVniCmd', basic_cmds, [None, None], [FileNotFoundError, FileNotFoundError]),
    # test data doesn't have evpn
    ('interfaceCmd', basic_cmds + ['top', 'aver'], [None, None, None, None], [1518, 143, 60, 0]),
    ('lldpCmd', basic_cmds, [None, None], [352, 48]),
    ('macsCmd', basic_cmds, [None, None], [312, 48]),
    ('mlagCmd', basic_cmds + ['describe'], [None, None, None], [44, NotImplementedError, 143]),
    ('ospfCmd', basic_cmds + ['top', 'aver'], [None, None, None, None],
     [FileNotFoundError, FileNotFoundError, FileNotFoundError, FileNotFoundError]),  # test data doesn't have OSPF
    ('routesCmd', basic_cmds + ['lpm'], [None, None, '10.0.0.1'], [2596, 66, 143]),
    ('systemCmd', basic_cmds, [None, None], [140, 130]),
    ('tablesCmd', basic_cmds, [None, 'system'], [14, 22]),
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
        if isinstance(sz, type) and isinstance(sz(), Exception):
            with pytest.raises(sz):
                execute_cmd(svc, cmd, arg)
        else:
            s = execute_cmd(svc, cmd, arg)
            assert isinstance(s, DataFrame)
            assert s.size == sz


def test_summary_exception(setup_nubia):
    s = None
    with pytest.raises(AttributeError):
        s = execute_cmd('systemCmd', 'foop', None)
    assert s is None


def execute_cmd(svc, cmd, arg):
    # expect the svc class are in the module svc and also named svc
    module = globals()[svc]
    instance = getattr(module, svc)()
    if arg is not None:
        return getattr(instance, cmd)(arg)
    else:
        return getattr(instance, cmd)()


@pytest.fixture
def setup_nubia():
    from suzieq.cli.sq_nubia_plugin import NubiaSuzieqPlugin
    from nubia import Nubia
    # monkey patching -- there might be a better way
    plugin = NubiaSuzieqPlugin()
    plugin.create_context = create_context

    # this is just so that context can be created
    shell = Nubia(name='test', plugin=plugin)


def create_context():
    config = create_context_config()
    context = NubiaSuzieqContext()
    context.cfg = config
    return context


def create_context_config():
    config = {'schema-directory': './suzeiq/config',
              'data-directory': './tests/data/basic_dual_bgp/parquet-out',
              'temp-directory': '/tmp/suzieq',
              'logging-level': 'WARNING'
              }
    return config
