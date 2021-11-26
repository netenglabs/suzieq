import asyncio
import errno
import fcntl
import logging
import os
import signal
from time import sleep

from suzieq.utils import ensure_single_instance, get_sq_install_dir


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
