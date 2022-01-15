import logging
from typing import List

from suzieq.shared.exceptions import DBNotFoundError
from suzieq.db.base_db import SqDB


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
    use_db = 'parquet'
    if table_name and table_name in cfg.get('db', {}):
        use_db = cfg['db'][table_name]
    elif dbname:
        use_db = dbname

    if not use_db:
        logger.error(f'Unable to find a DB for {table_name}/{dbname}')
        return None

    eng_mod = SqDB.get_plugins(use_db)
    if not eng_mod:
        raise DBNotFoundError('DB {use_db} not found')

    return eng_mod[use_db](cfg, logger)


def do_coalesce(cfg: dict, tables: List[str], period: str = '1h',
                logger: logging.Logger = None,
                no_sqpoller: bool = False) -> None:
    """The main coalescer routine, can run once or periodically.

    It calls the DB-specific coalescer. The period is necessary to pass to the
    DB coalescer even in case of run_once. By default the period is '1h'.

    :param cfg: dict, the SUzieq config dictionary
    :param tables: List[str], the list of tables to coalesce
    :param period: str, the string of how periodically the poller runs,
                   Examples are '1h', '1d' etc.
    :param run_once: bool, If true, run once and exit
    :param logger, logging.Logger, logger to use
    :param no_sqpoller: bool, ignore sqpoller
    :returns: dictionary of stats about coalescing
    :rtype: None

    """

    if not logger:
        logger = logging.getLogger()

    dbeng = get_sqdb_engine(cfg, None, 'parquet', logger)
    if not dbeng:
        logger.error('Unable to get DB object for DB parquet')
        raise DBNotFoundError

    return dbeng.coalesce(tables, period, no_sqpoller)
