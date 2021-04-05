import subprocess
from importlib.util import find_spec
import os


def gui_main():

    spec = find_spec('suzieq.gui')
    if spec:
        thisprog = f'{os.path.dirname(spec.loader.path)}/suzieq-gui.py'

    _ = subprocess.check_output(f'streamlit run {thisprog}'.split())


if __name__ == '__main__':
    gui_main()
