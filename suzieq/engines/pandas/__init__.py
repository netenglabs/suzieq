import os
from importlib.util import find_spec
from importlib import import_module
import inspect


def get_engine_object(table, baseobj):

    spec = find_spec('suzieq.engines.pandas')
    for file in spec.loader.contents():
        if (os.path.isfile(f'{os.path.dirname(spec.loader.path)}/{file}') and
                not file.startswith('_')):
            modname = file.split('.')[0]
            mod = import_module(f'suzieq.engines.pandas.{modname}')
            for mbr in inspect.getmembers(mod):
                if inspect.isclass(mbr[1]) and mbr[0] != 'SqPandasEngine':
                    fn = getattr(mbr[1], 'table_name', '')
                    if fn and fn() == table:
                        return mbr[1](baseobj)

    return None


__all__ = [get_engine_object]
