#!/usr/bin/env python3

import argparse
import asyncio
import os
import sys
import traceback
from typing import Dict

import uvloop

from suzieq.poller.worker.poller import Poller
from suzieq.poller.worker.writers.output_worker import OutputWorker
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import poller_log_params, init_logger, load_sq_config


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

    poller = None
    try:
        poller = Poller(userargs, cfg)
        await poller.init_poller()
        await poller.run()
    except (SqPollerConfError, InventorySourceError) as error:
        logger.error(error)
        print(error)
        sys.exit(1)


def worker_main():
    """The routine that kicks things off including arg parsing
    """
    # Get supported output, 'gather' cannot be manually selected
    supported_outputs = OutputWorker.get_plugins()
    if supported_outputs.get('gather', None):
        del supported_outputs['gather']
    supported_outputs = [k for k in supported_outputs]

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
    except Exception:  # pylint: disable=broad-except
        traceback.print_exc()

    sys.exit(0)


if __name__ == '__main__':
    worker_main()
