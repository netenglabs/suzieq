from nubia import context
from nubia import exceptions
from nubia import eventbus
import sys

from suzieq.utils import load_sq_config, Schema


class NubiaSuzieqContext(context.Context):
    def __init__(self, engine="pandas"):
        self.cfg = None
        self.schemas = None

        self.pager = False
        self.namespace = ""
        self.hostname = ""
        self.start_time = ""
        self.end_time = ""
        self.exec_time = ""
        self.engine = engine
        self.col_width = 50
        self.sort_fields = []
        self.view = ""
        super().__init__()

    def on_connected(self, *args, **kwargs):
        if self._args.config:
            self.cfg = load_sq_config(validate=True,
                                      config_file=self._args.config)
        else:
            self.cfg = load_sq_config(validate=True)
        if not self.cfg:
            sys.exit(1)
        self.schemas = Schema(self.cfg["schema-directory"])

    def on_cli(self, cmd, args):
        # dispatch the on connected message
        self.verbose = args.verbose
        self.registry.dispatch_message(eventbus.Message.CONNECTED)

    def on_interactive(self, args):
        self.verbose = args.verbose
        ret = self._registry.find_command("connect").run_cli(args)
        if ret:
            raise exceptions.CommandError("Failed starting interactive mode")
        # dispatch the on connected message
        self.registry.dispatch_message(eventbus.Message.CONNECTED)

    def change_engine(self, engine: str):
        '''This doesn't work at this time'''
        if engine == self.engine:
            return

        self.engine = engine
