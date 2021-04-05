#!/usr/bin/env python3

import sys
from nubia import Nubia, Options
from suzieq.cli.sq_nubia_plugin import NubiaSuzieqPlugin


def cli_main():
    plugin = NubiaSuzieqPlugin()
    shell = Nubia(name="suzieq", plugin=plugin,
                  options=Options(persistent_history=True))
    sys.exit(shell.run())


if __name__ == "__main__":
    cli_main()
