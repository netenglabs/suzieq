"""
This module contains the logic needed to start the poller
"""
import asyncio
import argparse
import os
import sys
from typing import Dict
import uvloop
import traceback

from suzieq.poller.controller.controller import Controller
from suzieq.poller.worker.writers.output_worker import OutputWorker
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import get_log_params, init_logger, load_sq_config


async def start_controller(user_args: argparse.Namespace, config_data: Dict):
    """Controller starting function

    This function loads all the plugins provided in the configuration file and
    coordinates all the different plugins

    Raises:
        RuntimeError: Invalid configuration file passed as parameter
        RuntimeError: Cannot find the configuration file
        RuntimeError: Missing inventorySource plugins in the configuration
    """
    # Init logger of the poller
    logfile, loglevel, logsize, log_stdout = get_log_params(
        'poller', config_data, '/tmp/sq-poller-controller.log')
    logger = init_logger('suzieq.poller.controller', logfile,
                         loglevel, logsize, log_stdout)

    try:
        controller = Controller(user_args, config_data)
        controller.init()
        await controller.run()
    except (SqPollerConfError, InventorySourceError, RuntimeError) as error:
        print(f"ERROR: {error}")
        logger.error(error)
        sys.exit(-1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Get supported output, 'gather' cannot be manually selected
    supported_outputs = OutputWorker.get_plugins()
    if supported_outputs.get('gather', None):
        del supported_outputs['gather']
    supported_outputs = [k for k in supported_outputs]

    # Two inputs are possible:
    # 1. Suzieq inventory file
    # 2. Input directory
    parser.add_argument(
        '-I',
        '--inventory',
        type=str,
        help='Input inventory file'
    )

    parser.add_argument(
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
        choices=['gather', 'process'],
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
        '--update-period',
        help='How frequently the inventory updates [DEFAULT=3600]',
        type=int
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
