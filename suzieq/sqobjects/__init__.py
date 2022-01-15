from typing import List
from suzieq.sqobjects.basicobj import SqObject


def get_tables() -> List[str]:
    """Return a list of all supported tables/services

    Returns:
        List[str]: sorted list of all supported tables/services
    """
    tables = SqObject.get_plugins()
    return sorted(tables.keys())


def get_sqobject(table_name: str):
    '''Return the object to operate on the table requested

    :param table_name: str, name of table for which object is requested
    :returns:
    :rtype: The child class of SqObject that corresponds to the table
            or raises ModuleNotFoundError if the table is not found

    '''

    tables = SqObject.get_plugins()
    if table_name not in tables:
        if table_name in ['interface', 'route', 'mac', 'table']:
            # Handle singular/plural conversion
            table_name += 's'

    if table_name not in tables:
        raise ModuleNotFoundError(f'Table {table_name} not found')

    return tables[table_name]


__all__ = get_tables() + ['get_sqobject']
