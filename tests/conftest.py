import pytest
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext


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
