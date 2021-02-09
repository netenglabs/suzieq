from pygments.token import Token

from nubia import context
from nubia import statusbar
from pandas import DataFrame

from suzieq.version import SUZIEQ_VERSION


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

        if context.get_context().pager:
            is_pager = (Token.Warn, "ON")
        else:
            is_pager = (Token.Info, "OFF")

        return [
            (Token.Toolbar, "Suzieq"),
            spacer,
            (Token.Toolbar, "Version "),
            spacer,
            (Token.Info, SUZIEQ_VERSION),
            spacer,
            (Token.Toolbar, "Pager "),
            spacer,
            is_pager,
            spacer,
            (Token.Toolbar, "Namespace "),
            spacer,
            (Token.Info, ", ".join(self.ctx.namespace)),
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
            (Token.Info, self.ctx.engine),
            spacer,
            (Token.Toolbar, "Query Time "),
            spacer,
            (Token.Info, self.ctx.exec_time),
        ]
