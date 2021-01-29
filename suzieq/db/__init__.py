
from importlib import import_module
import inspect
import logging


name = "sqdb"


def get_sqdb_engine(cfg: dict, table_name: str, dbname: str,
                    logger: logging.Logger):
    """Return the appropriate DB reader for the given table

    This function is dumb right now. Will get smarter as we add support for 
    more database readers.

    :param cfg: dict, Suzieq loaded config
    :param table_name: str, Name of the table you want to read
    :param dbname: str, specify the DB engine you want to get handle for
                   can be empty
    :param logger: logging.logger, the logger to use for logging
    :returns: the class that is the reader for this object
    :rtype: 
    """
    # Load the available engines
    avail_db = ['parquet']

    use_db = None
    if table_name and table_name in cfg.get('db', {}):
        use_db = cfg['db'][table_name]
    elif dbname and dbname in avail_db:
        use_db = dbname
    else:
        use_db = 'parquet'      # The default

    if not use_db:
        logger.error(f'Unable to find a DB for {table_name}/{dbname}')
        return None

    try:
        eng_mod = import_module(f'suzieq.db.{use_db}')
    except ModuleNotFoundError:
        return None

    for mbr in inspect.getmembers(eng_mod):
        if mbr[0] == 'get_sqdb' and inspect.isfunction(mbr[1]):
            return mbr[1](cfg, logger)

    return None


__all__ = [get_sqdb_engine]
