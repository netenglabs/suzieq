"""
This module contains all the logic needed to start and monitor the coalescer
"""
import asyncio
import errno
import logging
from pathlib import Path
from asyncio.subprocess import Process
from typing import Dict

from suzieq.poller.controller.utils.proc_utils import monitor_process
from suzieq.shared.exceptions import PollingError
from suzieq.shared.utils import get_sq_install_dir

logger = logging.getLogger(__name__)


class CoalescerLauncher:
    """CoalescerLauncher is the component in charge of start and monitor the
    running coalescer
    """

    def __init__(self,
                 config_file: str,
                 cfg: Dict,
                 coalescer_bin: str = None,
                 max_attempts: int = 3) -> None:
        """Initialize an instance of the CoalescerLauncher

        Args:
            config_file (str): the Suzieq configuration file to pass
                to the coalescer
            cfg (dict): the Suzieq config dictionary
            coalescer_bin (str, optional): optional path to coalescer binary.
                Defaults to None.
            max_attempts (int, optional): the number of attepts to perform
                for starting the coalescer. Defaults to 3
        """
        self.coalescer_process = None

        self.config_file = config_file
        self.cfg = cfg

        self.max_attempts = max_attempts
        if self.max_attempts <= 0:
            raise PollingError(
                'The number of attempts for starting the coalescer cannot be '
                '0 or less'
            )

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
        except asyncio.CancelledError:
            pass
        finally:
            # If the coalescer is still runnning we always need to terminate
            # it before exiting
            if self.coalescer_process and \
               self.coalescer_process.returncode is None:
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

        starting_attempts = 0

        # We would like to attempt the coalescer startup self.max_attempts
        # times
        while starting_attempts < self.max_attempts:
            if not self.coalescer_process:
                logger.info('Starting Coalescer')
            elif self.coalescer_process.returncode == errno.EBUSY:
                logger.warning('Trying to start coalescer')
            else:
                logger.warning('Restarting the coalescer')

            # Try to start the coalescer process
            self.coalescer_process = await self._start_coalescer()
            if not self.coalescer_process:
                raise PollingError('Unable to start the coalescer')

            # Check if we have something from the stdout we need to log
            await monitor_process(self.coalescer_process, 'COALESCER')

            # When the coalescer exists with EBUSY error, it means
            # there already is another instance of the coalescer running
            # we are fine with that, but we need to make sure it is always
            # running, so we wait some time before retrying launching again
            # the coalescer
            if self.coalescer_process.returncode == errno.EBUSY:
                logger.warning(
                    "There is a running coalescer instance, "
                    "let's try again later"
                )
                await asyncio.sleep(10*60)
            else:
                # The coalescer died for any other reason let's increase the
                # attempts counter
                starting_attempts += 1
        logger.error(
            f'Maximum number of attempts reached {self.max_attempts}/'
            f'{self.max_attempts}, the coalescer keep on crashing')

    async def _start_coalescer(self) -> Process:
        """Start the coalescer

        Returns:
            Process: the process object of the started coalescer.
        """
        coalescer_args = [self.coalescer_bin]
        if self.config_file:
            coalescer_args += ['-c', self.config_file]

        try:
            process = await asyncio.create_subprocess_exec(
                *coalescer_args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f'ABORTING. Unable to start coalescer: {ex}')
            process = None

        return process
