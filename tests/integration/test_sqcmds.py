import pytest

from pandas import DataFrame

from suzieq.cli.sqcmds import *
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext

# TODO
# checkin
#  make a new branch
#   make smaller dataset and see if things go faster
#  figure out code review
#  how do you make sure pipenv installs pytest?
# add commands to services with more commands
#  what do I do about commands that require parameters
# test parameters filtering
# go through aver/assert and figure out the different branches they are taking
# get pycharm remote debugging and testing working
# how does coverage work?
# is it possible to split the commands as different tests, rather than just the services?
# refactor sqcmds to not needs so much code -- this is a different task

basic_cmds= ['show', 'summarize']

# to add
# columns length, column names?
#  specific data?
@pytest.mark.parametrize("svc, commands, size", [
    ('addrCmd', basic_cmds, [324,18]),
    ('arpndCmd', basic_cmds, [592,48]),
    ('bgpCmd', basic_cmds, [352,143]),
    ('interfaceCmd', basic_cmds, [1518, 143]),
    ('lldpCmd', basic_cmds, [352,48]),
    ('macsCmd', basic_cmds, [312, 48]),
    ('mlagCmd', ['show', 'describe'], [44, 143]),
    ('routesCmd', basic_cmds, [2596, 66]),
    ('systemCmd', basic_cmds, [140, 130]),
    ('tablesCmd', ['show'], [14]), #don't know how to pass parameters, can't do describe
    ('topcpuCmd', basic_cmds, [42, 18]),
    ('topmemCmd', basic_cmds, [27, 18]),
    ('vlanCmd', basic_cmds, [96, 78])
])
def test_commands(setup_nubia, svc, commands, size):
    for cmd, sz in zip(commands, size):
        s = execute_cmd(svc, cmd)
        assert isinstance(s, DataFrame)
        assert s.size == sz


# TODO
# these need to move after we figure out a much better way of
#  dealing with missing data
@pytest.mark.parametrize("svc, commands", [
    ('evpnVniCmd', basic_cmds),
    ('ospfCmd', basic_cmds)
])
def test_missing_data(setup_nubia, svc, commands):
    for cmd in commands:
        with pytest.raises(FileNotFoundError):
            s = execute_cmd(svc, cmd)


def test_summary_exception(setup_nubia):
    s = None
    with pytest.raises(AttributeError):
        s = execute_cmd('systemCmd', 'foop')
    assert s is None


def execute_cmd(svc, cmd):
    # expect the svc class are in the module svc and also named svc
    module = globals()[svc]
    instance = getattr(module, svc)()
    return getattr(instance, cmd)()

@pytest.fixture
def setup_nubia():
    from suzieq.cli.sq_nubia_plugin import NubiaSuzieqPlugin
    from nubia import Nubia
    # monkey patching -- there must be a better way
    plugin = NubiaSuzieqPlugin()
    plugin.create_context = create_context

    # this is just so that context can be created
    shell = Nubia(name='test', plugin=plugin)


def create_context():
    config = create_config()
    context = NubiaSuzieqContext()
    context.cfg = config
    return context


def create_config():
    config = {'schema-directory': './suzeiq/config',
              'data-directory': './tests/data/basic_dual_bgp/parquet-out',
              'temp-directory': '/tmp/suzieq',
              'logging-level': 'WARNING'
              }
    return config
