import pytest
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext


commands = [('AddrCmd'), ('ArpndCmd'), ('BgpCmd'), ('EvpnVniCmd'), ('InterfaceCmd'), ('LldpCmd'), ('MacsCmd'),
    ('MlagCmd'), ('OspfCmd'), ('RoutesCmd'), ('SystemCmd'), ('TopcpuCmd'), ('TopmemCmd'), ('VlanCmd')]

tables = [('arpnd'), ('bgp'), ('evpnVni'), ('fs'), ('ifCounters'), ('interfaces'), ('lldp'), ('macs'), ('mlag'),
          ('ospfIf'), ('ospfNbr'), ('routes'), ('system'), ('time'), ('topcpu'), ('topmem'), ('vlan')]

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
              'data-directory': './tests/data/basic_dual_bgp/parquet-out',
              'temp-directory': '/tmp/suzieq',
              'logging-level': 'WARNING',
              'test_set': 'basic_dual_bgp'  # an extra field for testing
              }
    return config

@pytest.fixture
def get_schemas(create_context_config):
    from suzieq.utils import get_schemas
    schemas = get_schemas(create_context_config['schema-directory'])
    assert len(schemas) > 0
    return schemas
