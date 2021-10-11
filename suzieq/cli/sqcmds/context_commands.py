import typing
import os
from nubia import command, argument, context, CompletionDataSource
from nubia.internal.commands.help import HelpCommand
from nubia.internal.cmdbase import Command, AutoCommand
from prompt_toolkit.completion import Completion
from nubia.internal import parser
from termcolor import cprint, colored
from suzieq.sqobjects import get_tables


@command("set")
@argument("namespace", description="namespace to qualify selection")
@argument("hostname", description="Name of host to qualify selection")
@argument(
    "start_time", description="Start of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument("end_time", description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument("pager", description="Enable pagination prompt on longer outputs",
          choices=['on', 'off'])
@argument('col_width', description='Max Width of each column in table display')
@argument(
    "engine",
    choices=["pandas"],
    description="Use Pandas for non-SQL commands",
)
@argument(
    "datadir",
    description="Set the data directory for the command"
)
def set_ctxt(
        pager: str = 'on',
        hostname: typing.List[str] = [],
        start_time: str = "",
        end_time: str = "",
        namespace: typing.List[str] = [],
        engine: str = "",
        datadir: str = "",
        col_width: int = 50,
):
    """set certain contexts for subsequent commands. Cmd is additive"""
    plugin_ctx = context.get_context()

    if namespace:
        plugin_ctx.namespace = namespace

    if hostname:
        plugin_ctx.hostname = hostname

    if start_time:
        plugin_ctx.start_time = start_time

    if end_time:
        plugin_ctx.end_time = end_time

    if engine:
        plugin_ctx.change_engine(engine)

    if datadir:
        if os.path.isdir(datadir):
            plugin_ctx.cfg['data-directory'] = datadir
        else:
            print(f'{datadir} is not a valid directory')

    if col_width:
        plugin_ctx.col_width = int(col_width)

    if pager == 'on':
        plugin_ctx.pager = True


@command("clear")
@argument("namespace", description="namespace to qualify selection")
@argument("hostname", description="Name of host to qualify selection")
@argument(
    "start_time", description="Start of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument("end_time", description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument("pager", description="End of time window in YYYY-MM-dd HH:mm:SS format")
def clear_ctxt(
        pager: str = 'off',
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        namespace: str = "",
):
    """clear certain contexts for subsequent commands. Cmd is additive"""
    plugin_ctx = context.get_context()

    if namespace:
        plugin_ctx.namespace = []

    if hostname:
        plugin_ctx.hostname = []

    if start_time:
        plugin_ctx.start_time = ""

    if end_time:
        plugin_ctx.end_time = ""

    if pager:
        plugin_ctx.pager = False


class SqHelpCommand (Command):
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
            completions = [Completion(text=x, start_position=-len(document.text))
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
            cprint("Use "
                   f"{colored('help <name of command/service> [<verb>]', 'cyan')} "
                   "to get more help")
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
                self._allcmds[service].run_interactive(service, f'help', '')

    def _build_cmd_verb_list(self):
        if not self._allcmds:
            ctx = context.get_context()
            self._allcmds = ctx.registry.get_all_commands_map()
            self._sqcmds = [x for x in sorted(self._allcmds)
                            if not self._allcmds[x].built_in]
