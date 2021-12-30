#!/usr/bin/env python3
"""
This module contains the logic needed to start the poller
"""

import argparse
import asyncio
import os
import sys
import traceback
from typing import Dict

import uvloop
from suzieq.poller.controller.controller import Controller
from suzieq.poller.worker.writers.output_worker import OutputWorker
from suzieq.shared.exceptions import InventorySourceError, PollingError, \
    SqPollerConfError
from suzieq.shared.utils import poller_log_params, init_logger, load_sq_config


async def start_controller(user_args: argparse.Namespace, config_data: Dict):
    """Start the poller, this function launches the controller which
    spawns the poller workers

    Args:
        user_args (argparse.Namespace): the command line arguments
        config_data (Dict): the content of the Suzieq configuration file
    """
    # Init logger of the poller
    logfile, loglevel, logsize, log_stdout = poller_log_params(
        config_data,
        is_controller=True
    )
    logger = init_logger('suzieq.poller.controller', logfile,
                         loglevel, logsize, log_stdout)

    try:
        controller = Controller(user_args, config_data)
        controller.init()
        await controller.run()
    except (SqPollerConfError, InventorySourceError, PollingError) as error:
        print(f"ERROR: {error}")
        logger.error(error)
        sys.exit(-1)


def controller_main():
    """The routine that kicks things off including arg parsing
    """
    parser = argparse.ArgumentParser()

    # Get supported output, 'gather' cannot be manually selected
    supported_outputs = OutputWorker.get_plugins()
    if supported_outputs.get('gather', None):
        del supported_outputs['gather']
    supported_outputs = [k for k in supported_outputs]

    # Two inputs are possible:
    # 1. Suzieq inventory file
    # 2. Input directory
    source_arg = parser.add_mutually_exclusive_group()
    source_arg.add_argument(
        '-I',
        '--inventory',
        type=str,
        help='Input inventory file'
    )

    source_arg.add_argument(
        '-i',
        '--input-dir',
        type=str,
        help=('Directory where run-once=gather data is. Process the data in '
              'directory as they were retrieved by the hosts')
    )

    parser.add_argument(
        '-c',
        '--config',
        help='Controller configuration file',
        type=str
    )

    parser.add_argument(
        '-x',
        '--exclude-services',
        type=str,
        help='Exclude running this space separated list of services',
    )

    parser.add_argument(
        '--no-coalescer',
        default=False,
        action='store_true',
        help='Do not start the coalescer',
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
        "--output-dir",
        type=str,
        default=f'{os.path.abspath(os.curdir)}/sqpoller-output',
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        '--run-once',
        type=str,
        choices=['gather', 'process', 'update'],
        help=('Collect the data from the sources and terminates. gather store '
              'the output as it has been collected, process performs some '
              'processing on the data. Both cases store the results in a '
              'plain output file, one for each service.')
    )

    parser.add_argument(
        '-s',
        '--service-only',
        type=str,
        help='Only run this space separated list of services',
    )

    parser.add_argument(
        '--ssh-config-file',
        type=str,
        default=None,
        help='Path to ssh config file, that you want to use'
    )

    parser.add_argument(
        '-p',
        '--update-period',
        help='How frequently the inventory updates [DEFAULT=3600]',
        type=int
    )

    parser.add_argument(
        '-w',
        '--workers',
        type=int,
        help='Maximum number of workers to execute',
    )

    args = parser.parse_args()
    uvloop.install()
    cfg = load_sq_config(config_file=args.config)
    if not cfg:
        print("Could not load config file, aborting")
        sys.exit(1)

    try:
        asyncio.run(start_controller(args, cfg))
    except (KeyboardInterrupt, RuntimeError):
        pass
    except Exception:  # pylint: disable=broad-except
        traceback.print_exc()


if __name__ == '__main__':
    controller_main()
