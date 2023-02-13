#!/usr/bin/env python3

import argparse
import asyncio
import os
import sys
import traceback
from typing import Dict

import uvloop

from suzieq.poller.worker.worker import Worker
from suzieq.poller.worker.writers.output_worker import OutputWorker
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import (init_logger, load_sq_config, log_suzieq_info,
                                 poller_log_params)


async def start_worker(userargs: argparse.Namespace, cfg: Dict):
    """Start the poller worker

    Args:
        userargs (argparse.Namespace): the command line arguments
        cfg (Dict): the content of the Suzieq config file
    """
    # Init logger of the poller
    logfile, loglevel, logsize, log_stdout = poller_log_params(
        cfg,
        worker_id=userargs.worker_id
    )
    logger = init_logger('suzieq.poller.worker', logfile,
                         loglevel, logsize, log_stdout)

    log_suzieq_info('Poller Worker', logger)
    worker = None
    try:
        worker = Worker(userargs, cfg)
        await worker.init_worker()
        await worker.run()
    except (SqPollerConfError, InventorySourceError) as error:
        if not log_stdout:
            print(error)
        logger.error(error)
        sys.exit(1)
    except Exception as error:
        if not log_stdout:
            traceback.print_exc()
        logger.critical(f'{error}\n{traceback.format_exc()}')
        sys.exit(1)


def worker_main():
    """The routine that kicks things off including arg parsing
    """
    # Get supported output, 'gather' cannot be manually selected
    supported_outputs = OutputWorker.get_plugins()
    if supported_outputs.get('gather', None):
        del supported_outputs['gather']
    supported_outputs = list(supported_outputs.keys())

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-i',
        '--input-dir',
        type=str,
        help='Directory where run-once=gather data is'
    )

    parser.add_argument(
        '-o',
        '--outputs',
        nargs='+',
        default=['parquet'],
        choices=supported_outputs,
        type=str,
        help='Output formats to write to: parquet. Use '
        'this option multiple times for more than one output',
    )
    parser.add_argument(
        '-s',
        '--service-only',
        type=str,
        help='Only run this space separated list of services',
    )

    parser.add_argument(
        '-x',
        '--exclude-services',
        type=str,
        help='Exclude running this space separated list of services',
    )

    parser.add_argument(
        '-c',
        '--config',
        type=str, help='alternate config file'
    )

    parser.add_argument(
        '--run-once',
        type=str,
        choices=['gather', 'process', 'update'],
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default=f'{os.path.abspath(os.curdir)}/sqpoller-output',
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        '--ssh-config-file',
        type=str,
        default=None,
        help='Path to ssh config file, that you want to use'
    )

    parser.add_argument(
        '-n',
        '--worker-id',
        type=str,
        default='0',
        help=argparse.SUPPRESS,
    )

    userargs = parser.parse_args()

    uvloop.install()
    cfg = load_sq_config(config_file=userargs.config)
    if not cfg:
        print('Could not load config file, aborting')
        sys.exit(1)

    try:
        asyncio.run(start_worker(userargs, cfg))
    except (KeyboardInterrupt, RuntimeError):
        pass

    sys.exit(0)


if __name__ == '__main__':
    worker_main()
