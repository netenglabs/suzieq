#!/usr/bin/env python3

import sys
import os
import argparse
from time import sleep
import asyncio
import logging
from pathlib import Path
from collections import defaultdict
import getpass
import fcntl
import signal
import errno

import uvloop

from suzieq.poller.nodes import init_hosts, init_files
from suzieq.poller.services import init_services

from suzieq.poller.writer import init_output_workers, run_output_worker
from suzieq.utils import (load_sq_config, init_logger, ensure_single_instance,
                          get_sq_install_dir, get_log_params)


async def process_signal(signum, loop):
    tasks = [t for t in asyncio.all_tasks() if t is not
             asyncio.current_task()]

    for task in tasks:
        task.cancel()


def validate_parquet_args(cfg, output_args, logger):
    """Validate user arguments for parquet output"""

    if not cfg.get("data-directory", None):
        output_dir = "/tmp/suzieq/parquet-out/"
        logger.warning(
            "No output directory for parquet specified, using "
            "/tmp/suzieq/parquet-out"
        )
    else:
        output_dir = cfg["data-directory"]

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.isdir(output_dir):
        logger.error(
            "Output directory {} is not a directory".format(output_dir))
        print("Output directory {} is not a directory".format(output_dir))
        sys.exit(1)

    logger.info("Parquet outputs will be under {}".format(output_dir))
    output_args.update({"output_dir": output_dir})

    return


async def start_and_monitor_coalescer(config_file: str, cfg: dict,
                                      logger: logging.Logger,
                                      coalescer_bin: str = None) -> None:
    '''Start and monitor the coalescer

    :param config_file: str, the path to suzieq config file, to be passed
    :param cfg: dict, the Suzieq config dictionary
    :param logger: logging.Logger, pointer to logger to use
    :param coalescer_bin: str, optional path to coalescer binary

    :return: nothing

    '''

    async def start_coalescer():
        sq_path = get_sq_install_dir()
        coalescer_bin = f'{sq_path}/utilities/sq_coalescer.py'
        if config_file:
            coalescer_args = f'-c {config_file}'
        else:
            coalescer_args = ''
        coalescer_args = f'{coalescer_bin} {coalescer_args}'.strip().split()

        try:
            process = await asyncio.create_subprocess_exec(
                *coalescer_args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
        except Exception as ex:
            logger.error(f'ABORTING. Unable to start coalescer: {ex}')
            process = None

        return process

    fd = 0
    process = None
    # Check to see file lock is possible
    while not fd:
        if not process:
            logger.warning('Starting Coalescer')
        elif process.returncode == errno.EBUSY:
            logger.warning('Trying to start coalescer')
        process = await start_coalescer()

        if not process:
            os.kill(os.getpid(), signal.SIGTERM)
            return

        # Initial sleep to ensure that the coalescer starts up
        await asyncio.sleep(10)
        coalesce_dir = cfg.get('coalescer', {})\
            .get('coalesce-directory',
                 f'{cfg.get("data-directory")}/coalesced')

        fd = ensure_single_instance(f'{coalesce_dir}/.sq-coalescer.pid',
                                    False)
        if fd > 0:
            # unlock and try to start process
            try:
                fcntl.flock(fd, fcntl.F_UNLCK)
                os.close(fd)
            except OSError:
                pass
            continue

        # Check if we have something from the stdout we need to log
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            if process:
                process.terminate()
                sleep(5)
                process.kill()
            return

        if process.returncode and (process.returncode != errno.EBUSY):
            logger.error(f'coalescer stdout: {stdout}, stderr: {stderr}')
        else:
            if process.returncode == errno.EBUSY:
                await asyncio.sleep(10*60)
            else:
                logger.info(
                    f'coalescer ended stdout: {stdout}, stderr: {stderr}')

        fd = 0


async def start_poller(userargs, cfg):

    logfile, loglevel, logsize, log_stdout = get_log_params(
        'poller', cfg, '/tmp/sq-poller.log')
    logger = init_logger('suzieq.poller', logfile,
                         loglevel, logsize, log_stdout)

    if userargs.devices_file and userargs.namespace:
        logger.error("Cannot specify both -D and -n options")
        sys.exit(1)

    if not os.path.exists(cfg["service-directory"]):
        logger.error(
            "Service directory {} is not a directory".format(
                cfg['service-directory'])
        )
        print("Service directory {} is not a directory".format(
            cfg['service-directory']))
        sys.exit(1)

    if userargs.jump_host and not userargs.jump_host.startswith('//'):
        logger.error("Jump host format is //<username>@<jumphost>:<port>")
        print("Jump host format is //<username>@<jumphost>:<port>")
        sys.exit(1)

    if not cfg.get("schema-directory", None):
        schema_dir = "{}/{}".format(userargs.service_dir, "schema")
    else:
        schema_dir = cfg["schema-directory"]

    if userargs.ssh_config_file:
        ssh_config_file = os.path.expanduser(userargs.ssh_config_file)
        if (os.stat(
                os.path.dirname(
                    ssh_config_file)).st_mode | 0o40700 != 0o40700):
            logger.error('ssh directory has wrong permissions, must be 0700')
            print('ERROR: ssh directory has wrong permissions, must be 0700')
            sys.exit(1)

    output_args = {}

    if "parquet" in userargs.outputs:
        validate_parquet_args(cfg, output_args, logger)

    if userargs.run_once:
        userargs.outputs = ["gather"]
        output_args['output_dir'] = userargs.output_dir

    # Disable coalescer in specific, unusual cases
    # in case of input_dir, we also seem to leave a coalescer instance running
    if userargs.run_once or userargs.input_dir:
        userargs.no_coalescer = True

    outputs = init_output_workers(userargs.outputs, output_args)

    queue = asyncio.Queue()

    logger.info("Initializing hosts and services")
    tasks = []

    ignore_known_hosts = userargs.ignore_known_hosts or None

    # Retrieve the services to start
    svcs = list(Path(cfg["service-directory"]).glob('*.yml'))
    allsvcs = [os.path.basename(x).split('.')[0] for x in svcs]
    svclist = None

    if userargs.service_only:
        svclist = userargs.service_only.split()

        # Check if all the given services are valid
        notvalid = [s for s in svclist if s not in allsvcs]
        if notvalid:
            print(f'Invalid sevices specified: {notvalid}. '
                  f'Should have been one of {allsvcs}')
            exit(1)
    else:
        svclist = allsvcs

    if userargs.exclude_services:
        excluded_services = userargs.exclude_services.split()
        # Check if all the excluded services are valid
        notvalid = [e for e in excluded_services if e not in allsvcs]
        if notvalid:
            print(f'Services {notvalid} excluded, but they '
                  'are not valid services')
            exit(1)
        svclist = list(filter(lambda x: x not in excluded_services,
                              svclist))

    if not svclist:
        print("The list of services to execute is empty")
        sys.exit(1)

    connect_timeout = cfg.get('poller', {}).get('connect-timeout', 15)
    if userargs.input_dir:
        tasks.append(init_files(userargs.input_dir))
    else:
        tasks.append(init_hosts(inventory=userargs.devices_file,
                                ans_inventory=userargs.ansible_file,
                                namespace=userargs.namespace,
                                passphrase=userargs.passphrase,
                                jump_host=userargs.jump_host,
                                jump_host_key_file=userargs.jump_host_key_file,
                                password=userargs.ask_pass,
                                connect_timeout=connect_timeout,
                                ssh_config_file=userargs.ssh_config_file,
                                ignore_known_hosts=ignore_known_hosts))

    period = cfg.get('poller', {}).get('period', 15)

    tasks.append(init_services(cfg["service-directory"], schema_dir, queue,
                               svclist, period,
                               userargs.run_once or "forever"))

    nodes, svcs = await asyncio.gather(*tasks)

    if not nodes or not svcs:
        # Logging should've been done by init_nodes/services for details
        print('Terminating because no nodes or services found')
        sys.exit(0)

    node_callq = defaultdict(lambda: defaultdict(dict))

    node_callq.update({x: {'hostname': nodes[x].hostname,
                           'postq': nodes[x].post_commands}
                       for x in nodes})

    for svc in svcs:
        svc.set_nodes(node_callq)

    logger.setLevel(logging.INFO)
    logger.info("Suzieq Started")
    logger.setLevel(loglevel.upper())

    loop = asyncio.get_event_loop()
    for s in [signal.SIGTERM, signal.SIGINT]:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(process_signal(s, loop)))

    try:
        # The logic below of handling the writer worker task separately is to
        # ensure we can terminate properly when all the other tasks have
        # finished as in the case of using file input instead of SSH
        svc_tasks = [svc.run() for svc in svcs]
        tasks = [nodes[node].run() for node in nodes]
        tasks += [run_output_worker(queue, outputs, logger)]
        tasks += svc_tasks

        if not userargs.no_coalescer:
            tasks += [start_and_monitor_coalescer(userargs.config, cfg,
                                                  logger)]
        while tasks:
            try:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = list(pending)
                if tasks and any(i._coro in svc_tasks for i in tasks):
                    continue
                else:
                    break
            except asyncio.CancelledError:
                break
    finally:
        logger.warning("sq-poller: Received terminate signal. Terminating")
        loop.stop()
        return


def poller_main() -> None:

    supported_outputs = ["parquet"]

    parser = argparse.ArgumentParser()
    requiredgrp = parser.add_mutually_exclusive_group(required=True)
    requiredgrp.add_argument(
        "-D",
        "--devices-file",
        type=str,
        help="File with URL of devices to gather data from",
    )
    requiredgrp.add_argument(
        "-a",
        "--ansible-file",
        type=str,
        help="Ansible inventory file of devices to gather data from",
    )
    requiredgrp.add_argument(
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
    except Exception:
        import traceback
        traceback.print_exc()

    sys.exit(0)


if __name__ == '__main__':
    poller_main()
