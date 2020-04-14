import argparse
from suzieq.cli.sqcmds import *
from suzieq.cli.sqcmds import context_commands
from suzieq.cli.sqcmds import sqcmds_all
from suzieq.cli.sq_nubia_context import NubiaSuzieqContext
from suzieq.cli.sq_nubia_statusbar import NubiaSuzieqStatusBar
from nubia import PluginInterface, CompletionDataSource
from nubia.internal.blackcmd import CommandBlacklist
from nubia.internal.cmdbase import AutoCommand


class NubiaSuzieqPlugin(PluginInterface):
    """
    The PluginInterface class is a way to customize nubia for every customer
    use case. It allowes custom argument validation, control over command
    loading, custom context objects, and much more.
    """

    def create_context(self):
        """
        Must create an object that inherits from `Context` parent class.
        The plugin can return a custom context but it has to inherit from the
        correct parent class.
        """
        return NubiaSuzieqContext()

    def validate_args(self, args):
        """
        This will be executed when starting nubia, the args passed is a
        dict-like object that contains the argparse result after parsing the
        command line arguments. The plugin can choose to update the context
        with the values, and/or decide to raise `ArgsValidationError` with
        the error message.
        """
        pass

    def get_commands(self):
        cmds = [AutoCommand(getattr(globals()[x], x))
                for x in sqcmds_all if not x.startswith('_')]
        cmds.append(AutoCommand(context_commands.set_ctxt))
        cmds.append(AutoCommand(context_commands.clear_ctxt))
        return cmds

    def get_opts_parser(self, add_help=True):
        """
        Builds the ArgumentParser that will be passed to , use this to
        build your list of arguments that you want for your shell.
        """
        opts_parser = argparse.ArgumentParser(
            description="Suzieq CLI",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            add_help=add_help,
        )
        opts_parser.add_argument(
            "--config", "-c", default="", type=str, help="Configuration File"
        )
        opts_parser.add_argument(
            "--verbose",
            "-v",
            action="count",
            default=0,
            help="Increase verbosity, can be specified " "multiple times",
        )
        opts_parser.add_argument(
            "--stderr",
            "-s",
            action="store_true",
            default=True,
            help="By default the logging output goes to stderr "
            "Enable this feature to send it to a temporary logfile"
        )
        # we only support pandas now, so we don't want this option
        # opts_parser.add_argument(
        #    "--use-engine", "-e", help="Which analysis engine to use", default="pandas"
        # )
        return opts_parser

    def get_completion_datasource_for_global_argument(self, argument):
        if argument == "--config":
            return ConfigFileCompletionDataSource()
        if argument == "--use-engine":
            return ConfigEngineCompletionDataSource()
        return None

    def create_usage_logger(self, context):
        """
        Override this and return you own usage logger.
        Must be a subtype of UsageLoggerInterface.
        """
        return None

    def get_status_bar(self, context):
        """
        This returns the StatusBar object that handles the bottom status bar
        and the right-side per-line status
        """
        return NubiaSuzieqStatusBar(context)

    def getBlacklistPlugin(self):
        blacklister = CommandBlacklist()
        blacklister.add_blocked_command("topcpu")
        blacklister.add_blocked_command("topmem")
        return blacklister


class ConfigFileCompletionDataSource(CompletionDataSource):
    def get_all(self):
        return ["/tmp/c1", "/tmp/c2"]


class ConfigEngineCompletionDataSource(CompletionDataSource):
    def get_all(self):
        return ["pandas"]
