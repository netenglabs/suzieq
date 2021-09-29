from importlib.util import find_spec
from importlib import import_module
import inspect


name = "sqobjects"


def get_tables():
    fspec = find_spec('suzieq.sqobjects')
    tables = [x.split('.')[0] for x in fspec.loader.contents()
              if not x.startswith('_') and x != "basicobj.py"]
    tables.extend(['tables'])
    return tables


def get_sqobject(table_name: str):
    '''Return the object to operate on the table requested

    :param table_name: str, name of table for which object is requested
    :returns:
    :rtype: The child class of SqObject that corresponds to the table
            or raises ModuleNotFoundError if the table is not found

    '''

    try:
        mod = import_module(f'suzieq.sqobjects.{table_name}')
        for mbr in inspect.getmembers(mod):
            if inspect.isclass(mbr[1]):
                if getattr(mbr[1], '__bases__')[0].__name__ == 'SqObject':
                    return mbr[1]
    except ModuleNotFoundError:
        return None

    raise ModuleNotFoundError(f'{table_name} not found')


__all__ = get_tables() + ['get_sqobject']

sqobjs_all = __all__
