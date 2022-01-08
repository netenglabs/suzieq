import sys
import subprocess
import argparse
from importlib.util import find_spec
from pathlib import Path
import shlex

from suzieq.shared.utils import print_version


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
    userargs = parser.parse_args()

    if userargs.version:
        print_version()
        sys.exit(0)

    spec = find_spec('suzieq.gui')
    if spec:
        if userargs.framework == 'streamlit':
            thisprog = Path(spec.loader.path).parent / \
                'stlit' / 'suzieq-gui.py'

    if userargs.config:
        thisprog += f' -c {userargs.config}'

    _ = subprocess.check_output(shlex.split(f'streamlit run {thisprog}'))


if __name__ == '__main__':
    gui_main()
