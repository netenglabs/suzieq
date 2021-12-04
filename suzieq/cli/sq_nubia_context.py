import sys

from nubia import context
from nubia import exceptions
from nubia import eventbus

from suzieq.shared.utils import load_sq_config
from suzieq.shared.schema import Schema
from suzieq.shared.context import SqContext


class NubiaSuzieqContext(context.Context):
    '''Suzieq Nubia context setup on CLI startup'''

    def __init__(self, engine="pandas"):
        self.ctxt = SqContext()
        self.ctxt.engine = engine
        super().__init__()

    def on_connected(self, *args, **kwargs):
        if self._args.config:
            self.ctxt.cfg = load_sq_config(validate=True,
                                           config_file=self._args.config)
        else:
            self.ctxt.cfg = load_sq_config(validate=True)

        if not self.ctxt.cfg:
            sys.exit(1)
        self.ctxt.schemas = Schema(self.ctxt.cfg["schema-directory"])

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
