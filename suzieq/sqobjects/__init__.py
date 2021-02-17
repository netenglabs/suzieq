from importlib.util import find_spec
from importlib import import_module
import inspect


name = "sqobjects"


def _get_tables():
    fspec = find_spec('suzieq.sqobjects')
    tables = [x.split('.')[0] for x in fspec.loader.contents()
              if not x.startswith('_')]
    return tables


def get_sqobject(table_name: str):
    '''Return the object to operate on the table requested

    :param table_name: str, name of table for which object is requested
    :returns:
    :rtype: The child class of SqObject that corresponds to the table

    '''

    try:
        mod = import_module(f'suzieq.sqobjects.{table_name}')
        for mbr in inspect.getmembers(mod):
            if inspect.isclass(mbr[1]) and mbr[0] != 'SqObject':
                return mbr[1]
    except ModuleNotFoundError:
        return None


__all__ = _get_tables() + ['get_sqobject']

sqobjs_all = __all__
