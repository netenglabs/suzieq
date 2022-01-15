import sys

from nubia import context
from nubia import exceptions
from nubia import eventbus

from suzieq.shared.utils import load_sq_config, print_version
from suzieq.shared.schema import Schema
from suzieq.shared.context import SqContext


class NubiaSuzieqContext(context.Context):
    '''Suzieq Nubia context setup on CLI startup'''

    def __init__(self, engine="pandas"):
        self.ctxt = SqContext()
        self.ctxt.engine = engine
        super().__init__()

    def on_connected(self, *args, **kwargs):
        if self._args.V:
            print_version()
            sys.exit(0)
        if self._args.config:
            self.ctxt.cfg = load_sq_config(validate=True,
                                           config_file=self._args.config)
        else:
            self.ctxt.cfg = load_sq_config(validate=True)

        if not self.ctxt.cfg:
            print('ERROR: No suzieq configuration found')
            print('Create a suzieq-cfg.yml under the homedir or current dir')
            print('OR pass a path to the config file via -c argument')
            sys.exit(1)
        self.ctxt.schemas = Schema(self.ctxt.cfg["schema-directory"])
        cfg = self.ctxt.cfg
        self.ctxt.engine = cfg.get('ux', {}).get('engine', 'pandas')
        if self.ctxt.engine == 'rest':
            # See if we can extract the REST info from the REST part
            restcfg = cfg.get('rest', {})
            self.ctxt.rest_server_ip = restcfg.get('address', '127.0.0.1')
            self.ctxt.reset_server_port = restcfg.get('address', '80')
            if restcfg.get('no-https', 'False') == 'False':
                self.ctxt.transport = 'https'
            else:
                self.ctxt.transport = 'http'
            self.ctxt.rest_api_key = restcfg.get('API_KEY', '')

    def on_cli(self, cmd, args):
        # dispatch the on connected message
        self.registry.dispatch_message(eventbus.Message.CONNECTED)

    def on_interactive(self, args):
        ret = self._registry.find_command("connect").run_cli(args)
        if ret:
            raise exceptions.CommandError("Failed starting interactive mode")
        # dispatch the on connected message
        self.registry.dispatch_message(eventbus.Message.CONNECTED)

    def change_engine(self, engine: str):
        '''Change the backend engine'''
        if engine == self.ctxt.engine:
            return

        self.ctxt.engine = engine
