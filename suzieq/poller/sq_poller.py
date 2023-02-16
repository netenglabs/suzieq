#!/usr/bin/env python3
"""
This module contains the logic needed to start the poller
"""

import argparse
import asyncio
import sys
import traceback
from typing import Dict

import uvloop
from suzieq.poller.controller.controller import Controller
from suzieq.poller.worker.writers.output_worker import OutputWorker
from suzieq.shared.exceptions import InventorySourceError, PollingError, \
    SqPollerConfError
from suzieq.shared.utils import (poller_log_params, init_logger,
                                 load_sq_config, print_version,
                                 log_suzieq_info)
from suzieq.poller.controller.utils.inventory_utils import read_inventory


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
        if user_args.syntax_check:
            if not user_args.inventory:
                raise SqPollerConfError(
                    'With the --syntax-check option the user must specify '
                    'the inventory file via the -I option')
            # perform inventory validation and return
            read_inventory(user_args.inventory)
            print('Inventory syntax check passed')
            return

        log_suzieq_info('Poller Controller', logger, show_more=True)
        controller = Controller(user_args, config_data)
        controller.init()
        await controller.run()
    except (SqPollerConfError, InventorySourceError, PollingError) as error:
        if not log_stdout:
            print(f"ERROR: {error}")
        logger.error(error)
        sys.exit(1)
    except Exception as error:
        if not log_stdout:
            traceback.print_exc()
        logger.critical(f'{error}\n{traceback.format_exc()}')
        sys.exit(1)


def controller_main():
    """The routine that kicks things off including arg parsing
    """
    parser = argparse.ArgumentParser()

    # Get supported output, 'gather' cannot be manually selected
    supported_outputs = OutputWorker.get_plugins()
    if supported_outputs.get('gather', None):
        del supported_outputs['gather']
    supported_outputs = list(supported_outputs)

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
        '--debug',
        action='store_true',
        help='Build the node list and exit without polling the nodes'
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
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        '--run-once',
        type=str,
        choices=['gather', 'process', 'update'],
        help=('''The poller do not run forever, three modes are available:
        (1) gather: store the output as it has been collected,
        (2) process: performs some processing on the data.
        Both cases store the results in a plain output file,
        one for each service, and exit.
        (3) update: poll the nodes only once, write the result and stop''')
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
        help='The number of workers polling the nodes',
    )

    parser.add_argument(
        '-V',
        '--version',
        action='store_true',
        help='Print suzieq version'
    )

    parser.add_argument(
        '--syntax-check',
        action='store_true',
        help='Check inventory file syntax and return'
    )

    args = parser.parse_args()

    if args.version:
        print_version()
        sys.exit(0)

    uvloop.install()
    cfg = load_sq_config(config_file=args.config)
    if not cfg:
        print("Could not load config file, aborting")
        sys.exit(1)

    try:
        asyncio.run(start_controller(args, cfg))
    except (KeyboardInterrupt, RuntimeError):
        pass


if __name__ == '__main__':
    controller_main()
