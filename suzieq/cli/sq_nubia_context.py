from nubia import context
from nubia import exceptions
from nubia import eventbus

from suzieq.utils import load_sq_config, Schema
from suzieq.engines import get_sqengine


class NubiaSuzieqContext(context.Context):
    def __init__(self, engine="pandas"):
        self.cfg = load_sq_config(validate=True)

        self.schemas = Schema(self.cfg["schema-directory"])

        self.pager = False
        self.namespace = ""
        self.hostname = ""
        self.start_time = ""
        self.end_time = ""
        self.exec_time = ""
        self.engine_name = engine
        self.sort_fields = []
        self.engine = get_sqengine(engine)
        super().__init__()

    def on_connected(self, *args, **kwargs):
        if self._args.config:
            self.cfg = load_sq_config(validate=True,
                                      config_file=self._args.config)
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
        if engine == self.engine_name:
            return

        self.engine_name = engine
        self.engine = get_sqengine(engine)
