"""StaticPollerManager module

    This module contains a simple Manager which only writes
    inventory chunks on different files for the pollers
    and start them up
"""
import asyncio
import copy
import logging
import os
import shlex
from asyncio.subprocess import Process
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import aiofiles
import yaml
from cryptography.fernet import Fernet
from suzieq.poller.controller.inventory_async_plugin import \
    InventoryAsyncPlugin
from suzieq.poller.controller.manager.base_manager import Manager
from suzieq.poller.controller.utils.proc_utils import monitor_process
from suzieq.poller.worker.coalescer_launcher import CoalescerLauncher
from suzieq.shared.exceptions import PollingError, SqPollerConfError
from suzieq.shared.utils import get_sq_install_dir

logger = logging.getLogger(__name__)


class StaticManager(Manager, InventoryAsyncPlugin):
    """The StaticPollerManager writes the inventory chunks on files

    The number of pollers is defined in the configuration file with
    the path for inventory files
    """

    def __init__(self, config_data: Dict = None, validate: bool = True):

        super().__init__(config_data, validate)

        self._workers_count = config_data.get("workers", 1)

        # We need a pipeline thats at least as big as the number of workers
        # We need a pipeline that is at least as big as the number of workers
        self._max_cmd_pipeline = config_data.get('max-cmd-pipeline', 0)

        if self._max_cmd_pipeline:
            worker_cmd = int(self._max_cmd_pipeline / self._workers_count)
            os.environ['SQ_MAX_OUTSTANDING_CMD'] = str(worker_cmd)

        # Workers we are already monitoring
        self._running_workers = defaultdict(None)

        # Workers we do not monitor yet
        self._waiting_workers = defaultdict(None)

        # The currently applied chunks
        self._active_chunks = []
        self._poller_tasks_ready = asyncio.Event()

        # Get the running mode
        self._input_dir = config_data.get('input-dir', None)
        self._single_run_mode = config_data.get('single-run-mode', None)
        self._no_coalescer = config_data.get('no-coalescer', False)

        if not self._no_coalescer:
            self._coalescer_launcher = CoalescerLauncher(
                config_data['config'],
                config_data['config-dict']
            )

        # Configure the encyrption of the credential file
        if not self._input_dir:
            cred_key = Fernet.generate_key()
            self._encryptor = Fernet(cred_key)
            # Save the key into an env. variable
            os.environ['SQ_CONTROLLER_POLLER_CRED'] = cred_key.decode()

            # Configure the output directory for the inventory files
            path_name = f'/tmp/.suzieq/inventory.{os.getpid()}'
            self._inventory_path = Path(path_name).resolve()

            try:
                self._inventory_path.mkdir(parents=True, exist_ok=True)
            except FileExistsError:
                raise SqPollerConfError(
                    f'The inventory dir is not a directory: '
                    f'{self._inventory_path}'
                )

            os.environ['SQ_INVENTORY_PATH'] = str(self._inventory_path)

            self._inventory_file_name = 'inv'

        # Define poller parameters
        allowed_args = ['run-once', 'exclude-services', 'worker-cmd-pipeline',
                        'outputs', 'output-dir', 'service-only',
                        'ssh-config-file', 'config', 'input-dir']

        sq_path = get_sq_install_dir()
        self._args_to_pass = [f'{sq_path}/poller/worker/sq_worker.py']
        for arg, value in config_data.items():
            if arg in allowed_args and value:
                val_list = value if isinstance(value, list) else [value]
                self._args_to_pass.append(f'--{arg}', )
                # All the arguments should be string
                self._args_to_pass += [str(v) for v in val_list]

    @classmethod
    def get_data_model(cls):
        """This is only temporary. In future release I will add mananger
        validation via pydantic
        """
        raise NotImplementedError

    async def apply(self, inventory_chunks: List[Dict]):
        """Apply the inventory chyunks to the pollers

        Args:
            inventory_chunks (List[Dict]): input inventory chunks
        """

        tasks = []
        # In order to prevent any duplicate devices across the pollers, we
        # need to first stop all the pollers involved on the inventory change,
        # and only after all terminated, it is possible to restart them with
        # the new inventory
        pollers_to_launch = []
        n_chunks = len(inventory_chunks)
        if n_chunks != self._workers_count:
            raise PollingError(
                'The number of chunks is different than the number of workers'
            )

        if not self._active_chunks:
            pollers_to_launch = [*range(n_chunks)]
        else:
            for i, chunk in enumerate(inventory_chunks):
                if chunk != self._active_chunks[i]:
                    logger.info(f'Updating worker {i} chunk')
                    pollers_to_launch.append(i)

        # Create the inventory chunks and stop the pollers
        if pollers_to_launch:
            self._poller_tasks_ready.clear()

            logger.info(f'Writing inventory chunks {pollers_to_launch}')
            tasks = [self._write_chunk(i, inventory_chunks[i])
                     for i in pollers_to_launch]
            if self._active_chunks:
                tasks += [self._stop_poller(i) for i in pollers_to_launch]

            # Write the chunks and stop the pollers
            await asyncio.gather(*tasks)

            # Launch all the pollers we need to launch
            # If the mode is debug we do not need to launch the pollers
            if self._single_run_mode != 'debug':
                launch_tasks = [self._launch_poller(i)
                                for i in pollers_to_launch]
                res = await asyncio.gather(
                    *launch_tasks, return_exceptions=True)
                # Check if there are exceptions
                for r in res:
                    if r is not None and isinstance(r, Exception):
                        raise r
                # Copy the active inventory chunks in order to be able
                # to detect any following modifications
                self._active_chunks = copy.deepcopy(inventory_chunks)
            else:
                # When the debug mode is enabled print the instructions to
                # manually launch the workers
                self._print_poller_launch_instructions(n_chunks)
            self._poller_tasks_ready.set()

    async def launch_with_dir(self):
        """Launch a single poller writing the content of and input directory
        produced with the run-once=gather mode
        """
        if self._single_run_mode == 'debug':
            self._print_poller_launch_instructions()
        else:
            await self._launch_poller(0)
        self._poller_tasks_ready.set()

    def get_n_workers(self, _) -> int:
        """returns the content of self._workers_count statically loaded from
           the configuration file

        Attention: This function doesn't use the inventory

        Args:
            inventory (dict, optional): The global inventory.

        Returns:
            int: number of desired workers configured in the configuration
                 file
        """
        return self._workers_count

    async def _execute(self):
        poller_wait_tasks = {}
        tasks = []
        coalescer_task = None
        await self._poller_tasks_ready.wait()

        # Check if we need to start the coalescer
        if not self._no_coalescer:
            coalescer_task = asyncio.create_task(
                self._coalescer_launcher.start_and_monitor_coalescer()
            )
            tasks.append(coalescer_task)

        # pylint: disable=too-many-nested-blocks
        while self._waiting_workers or self._running_workers:
            if self._waiting_workers:
                # The list of tasks might contain some already terminated
                # workers, remove them before proceeding
                dead_workers = [w for k, w in poller_wait_tasks.items()
                                if k in self._waiting_workers]
                tasks = [t for t in tasks if t not in dead_workers]

                self._running_workers.update(self._waiting_workers)
                new_ptasks = {i: asyncio.create_task(
                    monitor_process(p, f'WORKER {i}'))
                    for i, p in self._waiting_workers.items()}
                poller_wait_tasks.update(new_ptasks)
                tasks += list(new_ptasks.values())
                self._waiting_workers = {}
            # Wait for the tasks
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            await self._poller_tasks_ready.wait()

            # Check if someone died and investigate why
            for d in done:
                if not self._no_coalescer and d == coalescer_task:
                    # Coalescer died
                    raise PollingError('Unexpected coalescer death')
                # Search for the poller who died
                poller_id = -1
                for i, p in poller_wait_tasks.items():
                    if p == d:
                        poller_id = i
                        break
                if poller_id >= 0:
                    if poller_id not in self._waiting_workers:
                        # Probably unexpected poller died
                        process = self._running_workers[poller_id]

                        if self._single_run_mode and process.returncode == 0:
                            # Worker natural death
                            del self._running_workers[poller_id]
                        else:
                            try:
                                d.result()
                                err = None
                            # pylint: disable=broad-except
                            except Exception as e:
                                err = str(e)

                            if self._single_run_mode:
                                logger.error(
                                    f'Unexpected worker {poller_id} death: '
                                    f'{err}')
                                del self._running_workers[poller_id]
                            else:
                                # We want gray failures to be hard failures in
                                # non-run-once mode
                                raise PollingError(
                                    f'Unexpected worker {poller_id} death:'
                                    f'{err}')
                else:
                    # Someone else died
                    raise PollingError('Unexpected task death')

            tasks = list(pending)

    async def _write_chunk(self, poller_id: int, chunk: Dict):
        """Write the chunk into an output file

        Args:
            id (int): id of the inventory chunk
            chunk (Dict): chunk of the inventory containing the dictionary
        """
        confidential_data = ['password', 'passphrase',
                             'ssh_keyfile', 'jump_host_key_file',
                             'enable_password']
        out_name = {}
        out_name['inv'] = (f'{str(self._inventory_path)}/'
                           f'{self._inventory_file_name}_{poller_id}.yml')
        out_name['cred'] = (f'{str(self._inventory_path)}/'
                            f'cred_{poller_id}')

        inventory_dict = {
            i: {k: v[k] for k in v if k not in confidential_data}
            for i, v in chunk.items()
        }

        inv_data = yaml.safe_dump(inventory_dict)
        if inv_data is None:
            raise PollingError(
                f'Unable to generate inventory file for worker {poller_id}'
            )
        async with aiofiles.open(out_name['inv'], "w") as out_file:
            await out_file.write(inv_data)

        credential_dict = {
            i: {k: v[k] for k in v if k in confidential_data}
            for i, v in chunk.items()
        }

        cred_data = yaml.safe_dump(credential_dict)
        if inv_data is None:
            raise PollingError(
                f'Unable to generate credential file for worker {poller_id}'
            )
        # Encrypt credential data
        enc_cred_data = self._encryptor.encrypt(cred_data.encode('utf-8'))
        async with aiofiles.open(out_name['cred'], "w") as out_file:
            await out_file.write(enc_cred_data.decode())

    async def _launch_poller(self, poller_id: int):
        """Launch a poller with the provided id and chunk, if a poller with
        the given id is already running, stop it and launch it again

        Args:
            id (int): id of the running poller
        """
        curr_args = [*self._args_to_pass, '--worker-id', str(poller_id)]

        # Launch the process
        process = await asyncio.create_subprocess_exec(
            *curr_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        if not process:
            raise PollingError('Unable to start the poller process')
        self._waiting_workers[poller_id] = process

    def _print_poller_launch_instructions(self, n_chunks: int = 1):
        """Print the commands to execute in order to manually launch
        the poller workers for debugging purpose.

        Args:
            n_chunks (int): the number of chunks the inventory is splitted into
        """
        quoted_args = [shlex.quote(v) for v in self._args_to_pass]
        args_str = ' '.join(quoted_args)
        if self._input_dir:
            print('You can manually start the worker with the following '
                  'command:')
            print()  # Print empty line
            print(f'python {args_str}')
        else:
            print(f'{n_chunks} inventory chunks generated, you can '
                  'now manually start the workers with the following '
                  'commands:')

            for i in range(n_chunks):
                print()  # Print an empty line
                env_to_print = ['SQ_CONTROLLER_POLLER_CRED',
                                'SQ_INVENTORY_PATH']
                if self._max_cmd_pipeline:
                    env_to_print.append('SQ_MAX_OUTSTANDING_CMD')
                for e in env_to_print:
                    print(f'export {e}={os.environ[e]}')

                args_to_print = args_str
                if i > 0:
                    args_to_print += f' --worker-id {i}'
                print(f'python {args_to_print}')

    async def _stop_poller(self, poller_id: int):
        """Kill the poller with the given id. The function first calls a
        SIGTERM, if the process do not exit after 5 seconds, a SIGKILL is sent.

        Args:
            poller_id (int): the poller id
        """
        current_poller = self._running_workers[poller_id]
        await self._stop_process(current_poller)

    async def _stop_process(self, process: Process):
        """Stop a process

        Args:
            process (Process): the process to stop
        """
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 5)
            except asyncio.TimeoutError:
                process.kill()

    async def _stop(self):
        # Stop all the processes
        running = list(self._running_workers.values())
        waiting = list(self._waiting_workers.values())
        tasks = [self._stop_process(p)
                 for p in [*running, *waiting]]
        await asyncio.gather(*tasks)
