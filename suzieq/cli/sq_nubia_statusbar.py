from pygments.token import Token

from nubia import context
from nubia import statusbar
from pandas import DataFrame


class NubiaSuzieqStatusBar(statusbar.StatusBar):
    def __init__(self, ctx):
        self._last_status = None
        self.ctx = ctx

    def get_rprompt_tokens(self):
        if not isinstance(self._last_status, DataFrame) and self._last_status:
            return [(Token.RPrompt, "Error: {}".format(self._last_status))]
        return []

    def set_last_command_status(self, status):
        self._last_status = status

    def get_tokens(self):
        spacer = (Token.Spacer, "  ")
        if context.get_context().verbose:
            is_verbose = (Token.Warn, "ON")
        else:
            is_verbose = (Token.Info, "OFF")
        return [
            (Token.Toolbar, "Suzieq"),
            spacer,
            (Token.Toolbar, "Verbose "),
            spacer,
            is_verbose,
            spacer,
            (Token.Toolbar, "Datacenter "),
            spacer,
            (Token.Info, ", ".join(self.ctx.datacenter)),
            spacer,
            (Token.Toolbar, "Hostname "),
            spacer,
            (Token.Info, ", ".join(self.ctx.hostname)),
            spacer,
            (Token.Toolbar, "StartTime "),
            spacer,
            (Token.Info, self.ctx.start_time),
            spacer,
            (Token.Toolbar, "EndTime "),
            spacer,
            (Token.Info, self.ctx.end_time),
            spacer,
            (Token.Toolbar, "Engine "),
            spacer,
            (Token.Info, self.ctx.engine_name),
            spacer,
            (Token.Toolbar, "Query Time "),
            spacer,
            (Token.Info, self.ctx.exec_time),
        ]
