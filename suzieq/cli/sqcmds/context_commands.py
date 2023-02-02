import typing
import os
from nubia import command, context
from nubia.internal.commands.help import HelpCommand
from nubia.internal.cmdbase import Command
from prompt_toolkit.completion import Completion
from termcolor import cprint, colored

from suzieq.cli.nubia_patch import argument
from suzieq.shared.utils import SUPPORTED_ENGINES, print_version


@command("set")
@argument("namespace", description="namespace to qualify selection")
@argument("hostname", description="Name of host to qualify selection")
@argument(
    "start_time",
    description="Start of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument("end_time",
          description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument("pager", description="Enable pagination prompt on longer outputs",
          choices=['on', 'off'])
@argument('col_width', description='Max Width of each column in table display')
@argument('max_rows',
          description='Max rows to display before ellipsis is shown')
@argument('all_columns',
          description='Display all columns wrapping around if necessary',
          choices=['yes', 'no'])
@argument(
    "engine",
    choices=SUPPORTED_ENGINES,
    description="What backend analyzer engine to use",
)
@argument(
    "debug", choices=['True', 'False'], description="Enable debug mode",
)
@argument(
    "datadir",
    description="Set the data directory for the command"
)
@argument(
    'rest_server_ip', description='IP address of the REST server'
)
@argument(
    'rest_server_port', description='Port of the REST server'
)
@argument(
    'rest_api_key', description='API key for the REST server'
)
@argument(
    'rest_use_https', description='Use HTTPS for the REST server',
    choices=['True', 'False']
)
def set_ctxt(
        pager: str = "",
        hostname: typing.List[str] = None,
        start_time: str = "",
        end_time: str = "",
        namespace: typing.List[str] = None,
        engine: str = "",
        datadir: str = "",
        debug: str = '',
        col_width: int = 50,
        max_rows: int = None,
        all_columns: str = None,
        rest_server_ip: str = "",
        rest_server_port: str = "",
        rest_api_key: str = "",
        rest_use_https: str = ""
):
    """set certain contexts for subsequent commands. Cmd is additive"""
    plugin_ctx = context.get_context()
    ctxt = plugin_ctx.ctxt

    if namespace:
        ctxt.namespace = namespace

    if hostname:
        ctxt.hostname = hostname

    if start_time:
        ctxt.start_time = start_time

    if end_time:
        ctxt.end_time = end_time

    if engine:
        plugin_ctx.change_engine(engine)

    if debug:
        ctxt.debug = debug == 'True'

    if datadir:
        if os.path.isdir(datadir):
            ctxt.cfg['data-directory'] = datadir
        else:
            print(f'{datadir} is not a valid directory')

    if col_width:
        ctxt.col_width = int(col_width)

    if max_rows is not None:
        if max_rows == 0:
            ctxt.max_rows = None
        else:
            ctxt.max_rows = max_rows

    if all_columns is not None:
        ctxt.all_columns = all_columns == "yes"

    if pager == 'on':
        ctxt.pager = True
    elif pager == 'off':
        ctxt.pager = False

    if rest_server_ip:
        ctxt.rest_server_ip = rest_server_ip

    if rest_server_port:
        ctxt.rest_server_port = rest_server_port

    if rest_api_key:
        ctxt.rest_api_key = rest_api_key

    if rest_use_https == 'True':
        ctxt.rest_transport = 'https'
    elif rest_use_https == 'False':
        ctxt.rest_transport = 'http'


@command("clear")
@argument("namespace", description="namespace to qualify selection")
@argument("hostname", description="Name of host to qualify selection")
@argument(
    "start_time",
    description="Start of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument("end_time",
          description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument("pager",
          description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument(
    "debug", choices=['True'], description="Disable debug mode",
)
def clear_ctxt(
        pager: str = 'off',
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        namespace: str = "",
        debug: str = '',
):
    """clear certain contexts for subsequent commands. Cmd is additive"""
    plugin_ctx = context.get_context()
    ctxt = plugin_ctx.ctxt

    if namespace:
        ctxt.namespace = []

    if hostname:
        ctxt.hostname = []

    if start_time:
        ctxt.start_time = ""

    if end_time:
        ctxt.end_time = ""

    if pager:
        ctxt.pager = False

    if debug:
        ctxt.debug = False


@command('version', help='print the suzieq version')
def sq_version():
    '''Print suzieq version'''
    print_version()


class SqHelpCommand (Command):
    '''Class to handle processing CLI help'''
    HELP = 'Get help on a command'
    thiscmd = ["help", "?"]

    def __init__(self):
        super().__init__()
        self._allcmds = self._sqcmds = None

    def run_interactive(self, cmd, args, raw):
        arglist = args.split()
        return self._help_cmd(*arglist)

    def get_command_names(self):
        return self.thiscmd

    def add_arguments(self, parser):
        parser.add_parser("help")

    def get_help(self, cmd, *args):
        return self.thiscmd[0]

    def get_completions(self, cmd, document, complete_event):
        exploded = document.text.lstrip().split(" ", 1)
        self._build_cmd_verb_list()
        if len(exploded) <= 1:
            if not document.text:
                return [Completion(x)
                        for x in self._sqcmds]
            completions = [Completion(text=x,
                                      start_position=-len(document.text))
                           for x in self._sqcmds
                           if x.startswith(document.text)]
            return completions

        service = exploded[0].lower()
        verb = exploded[1]

        verbs = [x[0].replace('aver', 'assert')
                 for x in self._allcmds[service].metadata.subcommands
                 if service in self._sqcmds]
        if not verb:
            return [Completion(x) for x in verbs]
        completions = [Completion(text=x, start_position=-len(verb))
                       for x in sorted(verbs)
                       if x.startswith(verb)]
        return completions

    def _help_cmd(self, *args):
        """Show help for a service"""
        if len(args) == 0:
            helpcmd = HelpCommand()
            helpcmd.run_interactive('', '', '')
            cprint(
                "Use "
                f"{colored('help <name of command/service> [<verb>]', 'cyan')}"
                " to get more help")
            cprint(f"For example: {colored('help route', 'cyan')}"
                   f" or {colored('help route show', 'cyan')}")
            return
        if len(args) == 1:
            service = args[0]
            verb = ''
        else:
            service = args[0]
            verb = args[1]

        self._build_cmd_verb_list()
        if service in self._sqcmds:
            if verb:
                self._allcmds[service].run_interactive(
                    service, f'help command={verb}', '')
            else:
                self._allcmds[service].run_interactive(service, 'help', '')

    def _build_cmd_verb_list(self):
        if not self._allcmds:
            ctx = context.get_context()
            self._allcmds = ctx.registry.get_all_commands_map()
            self._sqcmds = [x for x in sorted(self._allcmds)
                            if not self._allcmds[x].built_in]
