from pygments.token import Token

from nubia import statusbar
from pandas import DataFrame

from suzieq.version import SUZIEQ_VERSION


class NubiaSuzieqStatusBar(statusbar.StatusBar):
    '''Process CLI statusbar updates'''

    def __init__(self, ctxt):
        self._last_status = None
        self.ctxt = ctxt

    def get_rprompt_tokens(self):
        if not isinstance(self._last_status, DataFrame) and self._last_status:
            return [(Token.RPrompt, "Error: {}".format(self._last_status))]
        return []

    def set_last_command_status(self, status):
        self._last_status = status

    def get_tokens(self):
        spacer = (Token.Spacer, "  ")
        ctxt = self.ctxt.ctxt
        if ctxt.pager:
            is_pager = (Token.Warn, "ON")
        else:
            is_pager = (Token.Info, "OFF")

        if ctxt.engine != "rest":
            engine = ctxt.engine
        else:
            engine = (f'{ctxt.rest_server_ip}:'
                      f'{ctxt.rest_server_port}')
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
            (Token.Info, ", ".join(ctxt.namespace)),
            spacer,
            (Token.Toolbar, "Hostname "),
            spacer,
            (Token.Info, ", ".join(ctxt.hostname)),
            spacer,
            (Token.Toolbar, "StartTime "),
            spacer,
            (Token.Info, ctxt.start_time),
            spacer,
            (Token.Toolbar, "EndTime "),
            spacer,
            (Token.Info, ctxt.end_time),
            spacer,
            (Token.Toolbar, "Engine "),
            spacer,
            (Token.Info, engine),
            spacer,
            (Token.Toolbar, "Query Time "),
            spacer,
            (Token.Info, ctxt.exec_time),
        ]
