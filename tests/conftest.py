import pytest
import os
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext
from suzieq.poller.services import init_services
from unittest.mock import Mock


suzieq_cli_path = './suzieq/cli/suzieq-cli'


commands = [('AddrCmd'), ('ArpndCmd'), ('BgpCmd'), ('DeviceCmd'),
            ('EvpnVniCmd'),('InterfaceCmd'), ('LldpCmd'), ('MacCmd'),
            ('MlagCmd'), ('OspfCmd'), ('RouteCmd'),
            ('TopcpuCmd'), ('TopmemCmd'), ('VlanCmd')]

cli_commands = [('address'), ('bgp'), ('device'), ('evpnVni'),
            ('interface'), ('lldp'), ('mac'),
            ('mlag'), ('ospf'), ('path'), ('route'),
            ('yopcpuCmd'), ('topmem'), ('vlan')]


tables = [('arpnd'), ('bgp'), ('evpnVni'), ('device'), ('fs'), ('ifCounters'),
          ('interfaces'), ('lldp'), ('macs'), ('mlag'),
          ('ospfIf'), ('ospfNbr'), ('routes'), ('time'),
          ('topcpu'), ('topmem'), ('vlan')]


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
    return _get_schemas(create_context_config)


def _get_schemas(config):
    from suzieq.utils import get_schemas
    schemas = get_schemas(config['schema-directory'])
    assert len(schemas) > 0
    return schemas


@pytest.fixture
@pytest.mark.asyncio
def init_services_default(event_loop):
    configs = os.path.abspath(os.curdir) + '/config/'
    schema = configs + 'schema/'
    mock_queue = Mock()
    services = event_loop.run_until_complete(
        init_services(configs, schema, mock_queue, True))
    return services
