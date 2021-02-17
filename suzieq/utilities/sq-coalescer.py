#!/usr/bin/env python

from typing import List
import sys
import os
import errno
import argparse
import fcntl
from logging import Logger
from datetime import datetime
from time import sleep
from dataclasses import asdict
from dateparser import parse

import pandas as pd

from suzieq.utils import (load_sq_config, Schema, init_logger,
                          SchemaForTable, ensure_single_instance)
from suzieq.db import do_coalesce, get_sqdb_engine
from suzieq.version import SUZIEQ_VERSION


def run_coalescer(cfg: dict, tables: List[str], period: str, run_once: bool,
                  logger: Logger, no_sqpoller: bool = False) -> None:
    """Run the coalescer.

    Runs it once and returns or periodically depending on the
    value of run_once. It also writes out the coalescer records
    as a parquet file.

    :param cfg: dict, the Suzieq config file read in
    :param tables: List[str], list of table names to coalesce
    :param period: str, the string of how periodically the poller runs,
                   Examples are '1h', '1d' etc.
    :param run_once: bool, True if you want the poller to run just once
    :param logger: logging.Logger, the logger to write logs to
    :param no_sqpoller: bool, write records even when there's no sqpoller rec
    :returns: Nothing
    :rtype: none

    """

    try:
        schemas = Schema(cfg['schema-directory'])
    except Exception as ex:
        logger.error(f'Aborting. Unable to load schema: {str(ex)}')
        print(f'ERROR: Aborting. Unable to load schema: {str(ex)}')
        sys.exit(1)

    coalescer_schema = SchemaForTable('sqCoalescer', schemas)
    pqdb = get_sqdb_engine(cfg, 'sqCoalescer', None, logger)
    if not run_once:
        now = datetime.now()
        nextrun = parse(period, settings={'PREFER_DATES_FROM': 'future'})
        sleep_time = (nextrun-now).seconds
        logger.info(f'Got sleep time of {sleep_time} secs')

    while True:
        stats = do_coalesce(cfg, tables, period, logger, no_sqpoller)
        # Write the stats
        df = pd.DataFrame([asdict(x) for x in stats])
        if not df.empty:
            df['sqvers'] = coalescer_schema.version
            df['version'] = SUZIEQ_VERSION
            df['active'] = True
            df['namespace'] = ''
            pqdb.write('sqCoalescer', 'pandas', df, True,
                       coalescer_schema.get_arrow_schema(), None)

        if run_once:
            break
        sleep(sleep_time)


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

    userargs = parser.parse_args()

    cfg = load_sq_config(config_file=userargs.config)
    if not cfg:
        print(f'Invalid Suzieq config file {userargs.config}')
        sys.exit(1)

    logfile = cfg.get('coalescer', {}).get('logfile',
                                           '/tmp/sq-coalescer.log')
    loglevel = cfg.get('coalescer', {}).get('logging-level', 'DEBUG')
    logger = init_logger('suzieq.coalescer', logfile, loglevel, False)

    # Ensure we're the only compacter
    coalesce_dir = cfg.get('coalescer', {})\
                      .get('coalesce-directory',
                           f'{cfg.get("data-directory")}/coalesced')

    fd = ensure_single_instance(f'{coalesce_dir}/.sq-coalescer.pid',
                                False)
    if not fd:
        print(f'ERROR: Another coalescer process present')
        logger.error(f'Another coalescer process present')
        sys.exit(errno.EBUSY)

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

    run_coalescer(cfg, tables, timestr, userargs.run_once,
                  logger, userargs.no_sqpoller or False)
    os.truncate(fd, 0)
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        pass

    sys.exit(0)
