import os
from importlib.util import find_spec
from importlib import import_module
from pathlib import Path
import inspect

name = "sqengines"


def get_sqengine(engine_name: str, table_name: str):

    # Lets load the available engines
    try:
        eng_mod = import_module(f'suzieq.engines.{engine_name}')
    except ModuleNotFoundError:
        return None

    for mbr in inspect.getmembers(eng_mod):
        if mbr[0] == 'get_engine_object' and inspect.isfunction(mbr[1]):
            return mbr[1]

    return None


__all__ = [get_sqengine]
