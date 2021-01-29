#!/usr/bin/env python

import sys
import os
import time
import argparse
from typing import List
from dateparser import parse
from datetime import datetime
import fcntl

from suzieq.utils import load_sq_config, Schema, init_logger
from suzieq.db import get_sqdb_engine


def do_coalesce(cfg: dict, tables: List[str], period: str,
                run_once: bool, no_sqpoller: bool) -> None:
    """The main coalescer routine.
    It calls the DB-specific coalescer periodically

    :param cfg: dict, the SUzieq config dictionary
    :param tables: List[str], the list of tables to coalesce
    :param period: str, the interval at which the coalescer runs
    :param run_once: bool, If true, run once and exit
    :param no_sqpoller: bool, ignore sqpoller
    :returns: Nothing
    :rtype: None

    """
    logfile = cfg.get('coalescer', {}).get('logfile',
                                           '/tmp/sq-coalescer.log')
    loglevel = cfg.get('coalescer', {}).get('logging-level', 'WARNING')
    logger = init_logger('suzieq.coalescer', logfile, loglevel, False)

    if not run_once:
        now = datetime.now()
        nextrun = parse(period, settings={'PREFER_DATES_FROM': 'future'})
        sleep_time = (nextrun-now).seconds
        logger.info(f'Got sleep time of {sleep_time} secs')

    dbeng = get_sqdb_engine(cfg, None, 'parquet', logger)
    if not dbeng:
        logger.error('Unable to get DB object for DB parquet')
        sys.exit(1)

    while True:
        dbeng.coalesce(tables, period, no_sqpoller)
        if run_once:
            break
        time.sleep(sleep_time)


def ensure_single_instance() -> int:
    """Ensure there's only a single instance of a coalescer running

    Use a pid file with advisory file locking to assure this.

    :returns: 0 if True or pid of the other instance
    :rtype: int

    """
    fd = os.open('/tmp/sq-coalescer.pid', os.O_RDWR | os.O_CREAT, 0o600)
    pid = 0
    if fd:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.truncate(fd, 0)
            os.write(fd, bytes(str(os.getpid()), 'utf-8'))
        except IOError:
            # Looks like another process is running. Get its pid
            pid = os.read(fd, 12)

    if pid:
        try:
            pid = int(pid)
        except ValueError:
            pass

    return pid


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--service-only",
        type=str,
        help="Only run this space separated list of services",
    )
    parser.add_argument(
        "-x",
        "--exclude-services",
        type=str,
        help="Exclude running this space separated list of services",
    )

    parser.add_argument(
        "-c",
        "--config",
        default=f'{os.getenv("HOME")}/.suzieq/suzieq-cfg.yml',
        type=str, help="alternate config file"
    )
    parser.add_argument(
        "--run-once",
        default=False,
        help='Run the coalescer once and exit',
        action='store_true',
    )
    parser.add_argument(
        "-p",
        "--period",
        type=str,
        help=('Override the period specified in config file with this. '
              'Format is <period><h|d|w|y>. 1h is 1 hour, 2w is 2 weeks etc.')
    )
    parser.add_argument(
        "--no-sqpoller",
        action='store_true',
        help=argparse.SUPPRESS
    )

    # Ensure we're the only compacter
    pid_other = ensure_single_instance()
    if pid_other:
        print(f'ERROR: Another coalescer process with PID {pid_other} present')
        sys.exit(1)
    userargs = parser.parse_args()

    cfg = load_sq_config(config_file=userargs.config)
    if not cfg:
        print(f'Invalid Suzieq config file {userargs.config}')
        sys.exit(1)

    if userargs.run_once:
        timestr = ''
    elif not userargs.period:
        timestr = cfg.get('coalescer', {'period': '1h'}).get('period', '1h')
    else:
        timestr = userargs.period

    schemas = Schema(cfg.get('schema-directory'))
    if userargs.service_only or userargs.exclude_services:
        tables = [x for x in schemas.tables()
                  if (schemas.type_for_table(x) != "derivedRecord")]
        if userargs.service_only:
            tables = [x for x in tables if x in userargs.service_only.split()]
        if userargs.exclude_services:
            tables = [x for x in tables
                      if x not in userargs.exclude_services.split()]
    else:
        tables = []

    do_coalesce(cfg, tables, timestr, userargs.run_once,
                userargs.no_sqpoller or False)
