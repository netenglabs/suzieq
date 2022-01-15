#!/usr/bin/env python3

import sys
from nubia import Nubia, Options
from suzieq.cli.sq_nubia_plugin import NubiaSuzieqPlugin
from suzieq.cli import sqcmds


def cli_main():
    '''Kicks off the CLI run'''

    plugin = NubiaSuzieqPlugin()
    shell = Nubia(name="suzieq", plugin=plugin,
                  options=Options(persistent_history=True),
                  command_pkgs=sqcmds)
    sys.exit(shell.run())


if __name__ == "__main__":
    cli_main()
