import os
import sys
import subprocess
import argparse
from importlib.util import find_spec
from pathlib import Path

from colorama import init, Fore, Style
from suzieq.shared.utils import load_sq_config, print_version


def gui_main(*args):
    '''Kicks things off'''
    if not args:
        args = sys.argv

    parser = argparse.ArgumentParser(args)
    parser.add_argument(
        "-c",
        "--config",
        type=str, help="alternate config file",
        default=None
    )
    parser.add_argument(
        "-F",
        "--framework",
        type=str, help="Name of GUI framework to use",
        choices=['streamlit'],
        default='streamlit'
    )
    parser.add_argument(
        "--version",
        "-V",
        help="print Suzieq version",
        default=False, action='store_true',
    )
    parser.add_argument(
        "--port",
        "-p",
        help="http port to connect to",
        default='8501',
    )
    userargs = parser.parse_args()

    if userargs.version:
        print_version()
        sys.exit(0)

    spec = find_spec('suzieq.gui')
    if spec:
        if userargs.framework == 'streamlit':
            thisprog = Path(spec.loader.path).parent / \
                'stlit' / 'suzieq-gui.py'
            thisprog = str(thisprog)

    if userargs.port == '3000':
        # due to a streamlit issue, starting a server on port 3000 will cause
        # the SuzieQ gui to show an empty page
        # Issue: https://github.com/netenglabs/suzieq/issues/847
        print('Port 3000 is not allowed. Please choose a different port.\n\n'
              'For more details, check '
              'https://github.com/netenglabs/suzieq/issues/847')
        return

    # validate the config file before starting the gui
    load_sq_config(config_file=userargs.config)

    # write the sq_config file path inside an environment variable
    os.environ['SQ_GUI_CONFIG_FILE'] = userargs.config or ''

    init()
    with subprocess.Popen(['streamlit', 'run', thisprog,
                           '--server.port', userargs.port,
                           '--theme.base', 'light']) as p:
        print(Fore.CYAN + Style.BRIGHT +
              "\n  Starting Suzieq GUI" + Style.RESET_ALL)
        p.communicate()


if __name__ == '__main__':
    gui_main()
