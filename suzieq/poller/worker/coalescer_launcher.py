"""
This module contains all the logic needed to start and monitor the coalescer
"""
import asyncio
import errno
import fcntl
import logging
import os
import signal
from pathlib import Path
import shlex
from asyncio.subprocess import Process
from typing import Dict

try:
    from asyncio.exceptions import CancelledError
except ModuleNotFoundError:
    from asyncio import CancelledError

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
        self.coalescer_process = None

        self.config_file = config_file
        self.cfg = cfg
        self.coalescer_bin = coalescer_bin
        if not coalescer_bin:
            sq_path = get_sq_install_dir()
            self.coalescer_bin = Path(f'{sq_path}/utilities/sq_coalescer.py')

    @property
    def coalescer_pid(self) -> int:
        """The coalescer_pid is the PID of the coalescer process

        Returns:
            int: the pid of the coalescer process
        """

        return self.coalescer_process.pid if self.coalescer_process else None

    async def start_and_monitor_coalescer(self):
        """Start and monitor the coalescer
        """
        try:
            await self._monitor_coalescer()
        except CancelledError:
            pass
        finally:
            if self.coalescer_process:
                self.coalescer_process.terminate()
                try:
                    logger.warning('Waiting coalescer termination...')
                    await asyncio.wait_for(self.coalescer_process.wait(), 10)
                except asyncio.TimeoutError:
                    self.coalescer_process.kill()

    async def _monitor_coalescer(self):
        """This function calls _start_coalescer() and check if the process
        dies
        """
        fd = 0
        # Check to see file lock is possible
        while not fd:
            if not self.coalescer_process:
                logger.info('Starting Coalescer')
            elif self.coalescer_process.returncode == errno.EBUSY:
                logger.warning('Trying to start coalescer')

            # Try to start the coalescer process
            self.coalescer_process = await self._start_coalescer()

            if not self.coalescer_process:
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
            stdout, stderr = await self.coalescer_process.communicate()

            if self.coalescer_process.returncode and \
               (self.coalescer_process.returncode != errno.EBUSY):
                logger.error(f'coalescer stdout: {stdout}, stderr: {stderr}')
            else:
                if self.coalescer_process.returncode == errno.EBUSY:
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
        coalescer_args = shlex.split(coalescer_args_str.strip())

        try:
            process = await asyncio.create_subprocess_exec(
                *coalescer_args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f'ABORTING. Unable to start coalescer: {ex}')
            process = None

        return process
