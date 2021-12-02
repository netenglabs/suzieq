"""
This module contains all the logic needed to start and monitor the coalescer
"""
import asyncio
import errno
import fcntl
import logging
import os
import signal
from asyncio.subprocess import Process
from time import sleep
from typing import Dict

from suzieq.shared.utils import ensure_single_instance, get_sq_install_dir

logger = logging.getLogger(__name__)


class CoalescerLauncher:
    """CoalescerLauncher is the component in charge of start and monitor the
    running coalescer
    """
    def __init__(self,
                 config_file: str,
                 cfg: Dict,
                 coalescer_bin: str = None) -> None:
        """Initialize an instance of the CoalescerLauncher

        Args:
            config_file (str): the Suzieq configuration file to pass
                to the coalescer
            cfg (dict): the Suzieq config dictionary
            coalescer_bin (str, optional): optional path to coalescer binary.
                Defaults to None.
        """

        self.config_file = config_file
        self.cfg = cfg
        self.coalescer_bin = coalescer_bin
        if not coalescer_bin:
            sq_path = get_sq_install_dir()
            self.coalescer_bin = f'{sq_path}/utilities/sq_coalescer.py'

    async def start_and_monitor_coalescer(self):
        """Start and monitor the coalescer
            Args:
                config_file (str): the Suzieq configuration file to pass
                    to the coalescer
                cfg (dict): the Suzieq config dictionary
                coalescer_bin (str, optional): optional path to coalescer
                    binary. Defaults to None.
        """
        fd = 0
        process = None
        # Check to see file lock is possible
        while not fd:
            if not process:
                logger.info('Starting Coalescer')
            elif process.returncode == errno.EBUSY:
                logger.warning('Trying to start coalescer')

            # Try to start the coalescer process
            process = await self._start_coalescer()

            if not process:
                os.kill(os.getpid(), signal.SIGTERM)
                return

            # Initial sleep to ensure that the coalescer starts up
            await asyncio.sleep(10)
            coalesce_dir = self.cfg.get('coalescer', {})\
                .get('coalesce-directory',
                     f'{self.cfg.get("data-directory")}/coalesced')

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

    async def _start_coalescer(self) -> Process:
        """Start the coalescer

        Returns:
            Process: the process object of the started coalescer.
        """
        if self.config_file:
            coalescer_args_str = f'-c {self.config_file}'
        else:
            coalescer_args_str = ''
        coalescer_args_str = f'{self.coalescer_bin} {coalescer_args_str}'
        coalescer_args = coalescer_args_str.strip().split()

        try:
            process = await asyncio.create_subprocess_exec(
                *coalescer_args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
        except Exception as ex:
            logger.error(f'ABORTING. Unable to start coalescer: {ex}')
            process = None

        return process
