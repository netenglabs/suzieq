#!/usr/bin/env python3

import argparse
import asyncio
import getpass
import os
import sys
import traceback

import uvloop

from suzieq.poller.worker.poller import Poller
from suzieq.shared.exceptions import InventorySourceError, SqPollerConfError
from suzieq.shared.utils import get_log_params, init_logger, load_sq_config


async def start_poller(userargs, cfg):
    '''Start the poller'''
    # Init logger of the poller
    logfile, loglevel, logsize, log_stdout = get_log_params(
        'poller', cfg, f'/tmp/sq-poller-{userargs.worker_id}.log')
    logger = init_logger('suzieq.poller.worker', logfile,
                         loglevel, logsize, log_stdout)

    poller = None
    try:
        poller = Poller(userargs, cfg)
        await poller.init_poller()
        await poller.run()
    except (SqPollerConfError, InventorySourceError) as error:
        logger.error(error)
        print(f'ERROR: {error}')
        sys.exit(1)


def poller_main() -> None:
    '''The routine that kicks things off including arg parsing'''
    supported_outputs = ["parquet"]

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i",
        "--input-dir",
        type=str,
        help="Directory where run-once=gather data is"
    )

    parser.add_argument(
        "-n",
        "--namespace",
        type=str, required='--ansible-file' in sys.argv or "-a" in sys.argv,
        help="Namespace to associate for the gathered data"
    )
    parser.add_argument(
        "-o",
        "--outputs",
        nargs="+",
        default=["parquet"],
        choices=supported_outputs,
        type=str,
        help="Output formats to write to: parquet. Use "
        "this option multiple times for more than one output",
    )
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
        type=str, help="alternate config file"
    )

    parser.add_argument(
        "--run-once",
        type=str,
        choices=["gather", "process"],
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=f'{os.path.abspath(os.curdir)}/sqpoller-output',
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--ask-pass",
        default=False,
        action='store_true',
        help="prompt to enter password for login to devices",
    )
    parser.add_argument(
        "--passphrase",
        default=False,
        action='store_true',
        help="prompt to enter private key passphrase",
    )

    parser.add_argument(
        "--envpass",
        default="",
        type=str,
        help="Use named environment variable to retrieve password",
    )

    parser.add_argument(
        "-j",
        "--jump-host",
        default="",
        type=str,
        help="Jump Host via which to access the devices, IP addr/DNS hostname"
    )

    parser.add_argument(
        "-K",
        "--jump-host-key-file",
        default="",
        type=str,
        help="Key file to be used for jump host"
    )

    parser.add_argument(
        "-k",
        "--ignore-known-hosts",
        default=False,
        action='store_true',
        help="Ignore Known Hosts File",
    )

    parser.add_argument(
        "--ssh-config-file",
        type=str,
        default=None,
        help="Path to ssh config file, that you want to use"
    )

    parser.add_argument(
        "--no-coalescer",
        default=False,
        action='store_true',
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--worker-id",
        type=str,
        default='0',
        help=argparse.SUPPRESS,
    )

    userargs = parser.parse_args()

    if userargs.passphrase:
        userargs.passphrase = getpass.getpass(
            'Passphrase to decode private key file: ')
    else:
        userargs.passphrase = None

    if userargs.ask_pass:
        userargs.ask_pass = getpass.getpass(
            'Password to login to device: ')
    else:
        userargs.ask_pass = None

    if userargs.envpass:
        passwd = os.getenv(userargs.envpass, '')
        if not passwd:
            print(
                f'ERROR: No password in environment '
                f'variable {userargs.envpass}')
            sys.exit(1)
        userargs.ask_pass = passwd

    uvloop.install()
    cfg = load_sq_config(config_file=userargs.config)
    if not cfg:
        print("Could not load config file, aborting")
        sys.exit(1)

    try:
        asyncio.run(start_poller(userargs, cfg))
    except (KeyboardInterrupt, RuntimeError):
        pass
    except Exception:  # pylint: disable=broad-except
        traceback.print_exc()

    sys.exit(0)


if __name__ == '__main__':
    poller_main()
