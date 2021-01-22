import os
from importlib.util import find_spec
from importlib import import_module
from pathlib import Path
import inspect

name = "sqengines"


def get_sqengine(name: str = "pandas"):

    # Lets load the available engines
    engines = {}
    for ent in Path(os.path.dirname(find_spec('suzieq.engines')
                                    .loader.path)).iterdir():
        if ent.is_dir() and not ent.name.startswith('_'):
            engine = os.path.basename(os.path.basename(ent))
            eng_mod = import_module(f'suzieq.engines.{engine}')
            for mbr in inspect.getmembers(eng_mod):
                if inspect.isclass(mbr[1]):
                    engines[engine] = mbr[1]

    if name in engines:
        return engines[name]

    return None


__all__ = [get_sqengine]
