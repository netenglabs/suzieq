from datetime import datetime
import time
import logging
from dateparser import parse
from typing import List
from importlib import import_module
import inspect

from suzieq.exceptions import DBNotFoundError


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


def do_coalesce(cfg: dict, tables: List[str], period: str = '1h',
                run_once: bool = False, no_sqpoller: bool = False,
                logger: logging.Logger = None) -> None:
    """The main coalescer routine, can run once or periodically.

    It calls the DB-specific coalescer. If invoked with a period,
    it runs forever. If you want it to run just once, set run_once
    to True. The period is necessary to pass to the DB coalescer even
    in case of run_once. By default the period is '1h'.

    :param cfg: dict, the SUzieq config dictionary
    :param tables: List[str], the list of tables to coalesce
    :param period: str, the string of how periodically the poller runs,
                   Examples are '1h', '1d' etc.
    :param run_once: bool, If true, run once and exit
    :param no_sqpoller: bool, ignore sqpoller
    :param logger, logging.Logger, logger to use
    :returns: Nothing
    :rtype: None

    """

    if not logger:
        logger = logging.getLogger()

    if not run_once:
        now = datetime.now()
        nextrun = parse(period, settings={'PREFER_DATES_FROM': 'future'})
        sleep_time = (nextrun-now).seconds
        logger.info(f'Got sleep time of {sleep_time} secs')

    dbeng = get_sqdb_engine(cfg, None, 'parquet', logger)
    if not dbeng:
        logger.error('Unable to get DB object for DB parquet')
        raise DBNotFoundError

    while True:
        dbeng.coalesce(tables, period, no_sqpoller)
        if run_once:
            break
        time.sleep(sleep_time)
