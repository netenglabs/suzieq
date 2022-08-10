"""
This module implements all the logic related to initialization of the services
"""
import asyncio
import logging
import os
from collections import defaultdict
from pathlib import Path
from time import struct_time
from typing import Callable, Dict, List, Union

import textfsm
import yaml
from genericpath import isfile
from suzieq.db.base_db import SqDB

from suzieq.poller.worker.services.service import Service
from suzieq.shared.exceptions import SqPollerConfError
from suzieq.shared.schema import Schema, SchemaForTable

logger = logging.getLogger(__name__)
BLACKLIST_SERVICES = ['ifCounters', 'topmem', 'topcpu']


class ServiceManager:
    """Service manager is the component in charge of the
    Services setup and initialization.
    """

    def __init__(self,
                 add_task_fn: Callable,
                 service_directory: str,
                 schema_dir: str,
                 output_queue: asyncio.Queue,
                 run_mode: str,
                 cfg: Dict,
                 default_interval: int = 15,
                 **kwargs) -> None:
        """Instantiate an instance of the ServiceManager class

        Args:
            add_task_fn (Callable): the function to call to schedule
                a task in the poller.
            service_directory (str): the directory where services are
                described.
            schema_dir (str): the directory containing the schema of the
                tables of the services.
            output_queue (asyncio.Queue): it is the queue where the services
                are supposed to write to make a writer persist the output of
                a command.
            run_mode (str): a string representing the running policy:
                - gather (run once): gather the output without processing
                - processing (run once): gather the output and process it
                - forever: periodically poll the nodes.
            default_interval (int): the default time execution interval.
        """

        self._services = []
        self._running_svcs = []
        self.add_task_fn = add_task_fn
        self.output_queue = output_queue
        self.default_interval = default_interval
        self.run_mode = run_mode
        self.cfg = cfg
        self.outputs = kwargs.pop('outputs', [])

        # Set and validate service and schema directories
        if not os.path.isdir(service_directory):
            raise SqPollerConfError(
                f"Service directory {service_directory} is not a directory"
            )
        self.service_directory = service_directory
        self.schema_dir = schema_dir
        if not self.schema_dir:
            self.schema_dir = '{}/{}'.format(service_directory, 'schema')
        if not os.path.isdir(self.schema_dir):
            raise SqPollerConfError(
                f"Service directory {self.schema_dir} is not a directory"
            )

        # Build the list of services to execute
        service_only = kwargs.pop('service_only', '')
        exclude_services = kwargs.pop('exclude_services', '')
        self._svcs_list = self._get_service_list(service_only,
                                                 exclude_services)

    @property
    def services(self) -> List[Service]:
        """Get the list of Service objects

        Returns:
            List[Service]: list of the instantiated Service
                objects, returns an empty list if the init_services()
                has not been called.
        """
        return self._services

    @property
    def svcs_list(self) -> List[str]:
        """Get the list of the name of the services

        Returns:
            List[str]: a list of string containing the name of the services
                selected for execution
        """
        return self._svcs_list

    @property
    def running_services(self) -> List[Callable]:
        """Get the list of running services

        Returns:
            List[Callable]: the list of coroutines of the running
                services.
        """
        return self._running_svcs

    @staticmethod
    def get_service_list(service_only: str,
                         exclude_services: str,
                         service_directory: struct_time) -> List[str]:
        """Constuct the list of the name of the services to be started
        in the poller, according to the arguments passed by the user.
        Returns a InvalidAttribute exception if any of the passed service
        is invalid.

        Args:
            service_only (str): take only the services in the space-separated
                list
            exclude_service (List[str]): remove the given services from the
                space-separated service list
            service_directory (str): the directory where services are defined

        Raises:
            SqPollerConfError: raised in case of wrong service name in
            'include only' or exclude list

        Returns:
            List[str]: the list of services to executed in the poller
        """

        if not os.path.isdir(service_directory):
            raise SqPollerConfError(
                'The service directory provided is not a directory'
            )

        svcs = list(Path(service_directory).glob('*.yml'))
        allsvcs = [s_name for s in svcs
                   if (s_name := os.path.basename(s).split('.')[0])
                   not in BLACKLIST_SERVICES]
        svclist = None

        if service_only:
            svclist = service_only.split()

            # Check if all the given services are valid
            notvalid = [s for s in svclist if s not in allsvcs]
            if notvalid:
                raise SqPollerConfError(f'Invalid svcs specified: {notvalid}. '
                                        f'Should have been one of {allsvcs}')
        else:
            svclist = allsvcs

        if exclude_services:
            excluded_services = exclude_services.split()
            # Check if all the excluded services are valid
            notvalid = [e for e in excluded_services if e not in allsvcs]
            if notvalid:
                raise SqPollerConfError(f'Services {notvalid} excluded, but '
                                        'they are not valid.')
            svclist = list(filter(lambda x: x not in excluded_services,
                                  svclist))

        if not svclist:
            raise SqPollerConfError('The list of services to execute is empty')
        return svclist

    async def init_services(self) -> List[Service]:
        """Instantiate Service objects and prepare
        them for running. This function should be called before
        scheduling the service for running.

        Returns:
            List[Service]: the list of the initialized service instances
        """
        services = []
        schemas = defaultdict(dict)
        svc_classes = Service.get_plugins()

        schemas = Schema(self.schema_dir)
        if schemas:
            poller_schema = schemas.get_arrow_schema('sqPoller')
            poller_schema_version = SchemaForTable('sqPoller', schemas).version

        db_access = self._get_db_access(self.cfg)

        # Read the available services and iterate over them, discarding
        # the ones we do not need to instantiate
        svc_desc_files = Path(self.service_directory).glob('*.yml')

        for filename in svc_desc_files:
            with open(filename, 'r') as f:
                svc_def = yaml.safe_load(f.read())

            if not svc_def:
                logger.warning(f'Skip empty service file: {filename}')
                continue

            service = svc_def.get('service')
            if service in BLACKLIST_SERVICES:
                continue

            if all(service not in x for x in [self.svcs_list]):
                logger.warning(
                    f"Ignoring unspecified service {svc_def.get('service')}"
                )
                continue

            if 'service' not in svc_def or 'apply' not in svc_def:
                logger.error(
                    'Ignoring invalid service file definition.'
                    f"'service' and 'apply' keywords: {filename}"
                )
                continue

            period = svc_def.get('period', self.default_interval)
            for nos, cmds_desc in svc_def['apply'].items():

                # Check if the the current nos copies from another
                if isinstance(cmds_desc, dict) and 'copy' in cmds_desc:
                    newval = svc_def['apply'].get(cmds_desc['copy'], None)
                    if not newval:
                        logger.error(
                            f"No device type {cmds_desc['copy']} to copy from,"
                            f"for {nos} for service {svc_def['service']}"
                        )
                        return
                    cmds_desc = newval

                # Update the command description adding the
                # specification for the output parsing
                if isinstance(cmds_desc, list):
                    for subele in cmds_desc:
                        self._parse_nos_version(filename, svc_def, nos, subele)
                else:
                    self._parse_nos_version(filename, svc_def, nos, cmds_desc)

            try:
                schema = SchemaForTable(svc_def['service'], schema=schemas)
            except Exception:  # pylint: disable=broad-except
                logger.error(f"No matching schema for {svc_def['service']}")
                continue

            if schema.type == 'derivedRecord':
                # These are not real services and so ignore them
                continue

            # Valid service definition, add it to list
            # if the service has not a dedicated class, we will use the
            # default implementation
            class_to_use = svc_classes.get(svc_def['service'], Service)
            service = class_to_use(
                svc_def['service'],
                svc_def['apply'],
                period,
                svc_def.get('type', 'state'),
                svc_def.get('keys', []),
                svc_def.get('ignore-fields', []),
                schema,
                self.output_queue,
                db_access,
                self.run_mode
            )
            service.poller_schema = poller_schema
            service.poller_schema_version = poller_schema_version
            logger.info(f'Service {service.name} added')
            services.append(service)

        # Once done set the service list and return its content
        self._services = services
        return self._services

    async def schedule_services_run(self):
        """Schedule the services tasks in the poller, so that they can
        start sending command queries to the nodes.

        This function should be called only once, if called more
        than once, it won't have any effect.
        """
        self._running_svcs = [svc.run() for svc in self.services]
        await self.add_task_fn(self._running_svcs)

    async def set_nodes(self, node_callq: Dict):
        """Set/Update the list of nodes to poll

        Args:
            node_callq (Dict): a dictionary having, for each
                'namespace.hostname' the node hostname and the function
                allowing to calla query on the node.
        """
        for svc in self._services:
            await svc.set_nodes(node_callq)

    def _get_db_access(self, cfg) -> SqDB:
        """Return the SqDB to use to access to the state of the previous
        polls

        Raises:
            DBNotFoundError: raised if not plugin for the given outputs is
                found

        Returns:
            SqDB: the SqBB object to use for data access
        """
        if not self.outputs:
            return None
        # Remove gather from the outputs, since with it we only write in files
        candidate_out = [o for o in self.outputs if o != 'gather']
        if candidate_out:
            dbs = SqDB.get_plugins()
            # Get only the first out as source
            outdb = candidate_out[0]
            if outdb not in dbs:
                raise SqPollerConfError(f'{outdb} database not found')
            # Init the SqDB object
            return dbs[outdb](cfg, logger)
        return None

    def _get_service_list(self,
                          service_only: str,
                          exclude_services: str) -> List[str]:
        """Call the get_service_directory static method to constuct the list
        of the name of the services to be started.

        Args:
            service_only (str): take only the services in the space-separated
                list
            exclude_service (List[str]): remove the given services from the
                space-separated service list

        Raises:
            SqPollerConfError: raised in case of wrong service name in
            'include only' or exclude list

        Returns:
            List[str]: the list of services to executed in the poller
        """
        return self.get_service_list(service_only,
                                     exclude_services,
                                     self.service_directory)

    # pylint: disable=unused-argument
    def _parse_nos_version(self,
                           filename: str,
                           svc_def: Dict,
                           nos: str,
                           cmds_desc: Union[Dict, List]):
        """Given a command description check whether initialize the textfsm
        finite state machine for the output parsing, if needed.

        Args:
            filename (str): the name of the file describing the service
            svc_def (Dict): the definition of the service
            nos (str): the nos version the commands are related to
            cmds_desc (Union[Dict, List]): the description fo the commands to
                execute.
        """
        # pylint: disable=too-many-boolean-expressions
        if ('command' not in cmds_desc) or (
                (
                    isinstance(cmds_desc['command'], list)
                    and not all('textfsm' in x or 'normalize' in x
                                for x in cmds_desc['command'])
                )
                or (
                    not isinstance(cmds_desc['command'], list)
                    and ('normalize' not in cmds_desc
                         and 'textfsm' not in cmds_desc)
                )
        ):
            logger.error(
                'Ignoring invalid service file '
                "definition. Need both 'command' and "
                f"'normalize/textfsm' keywords: {filename}, {cmds_desc}"
            )
            return

        if 'textfsm' in cmds_desc:
            # We may have already visited this element and parsed
            # the textfsm file. Check for this and in this case return
            if cmds_desc['textfsm'] and isinstance(
                cmds_desc['textfsm'], textfsm.TextFSM
            ) or (cmds_desc['textfsm'] is None):
                return

            # Read the file and create the textfsm in the cmd description
            tfsm_file = self.service_directory + '/' + cmds_desc['textfsm']
            if not isfile(tfsm_file):
                logger.error(
                    f'Textfsm file {tfsm_file} not found. Ignoring service'
                )
                return

            with open(tfsm_file, 'r') as f:
                tfsm_template = textfsm.TextFSM(f)
                cmds_desc['textfsm'] = tfsm_template
        if isinstance(cmds_desc['command'], list):
            # If the command description is a list of commands
            # we need to iterate over them
            for subelem in cmds_desc['command']:
                if 'textfsm' in subelem:
                    # Check if the elemnt has been already visited
                    if subelem['textfsm'] and isinstance(
                        subelem['textfsm'], textfsm.TextFSM
                    ):
                        continue

                    tfsm_file = (f"{self.service_directory}/"
                                 f"{subelem['textfsm']}")
                    if not isfile(tfsm_file):
                        logger.error(
                            f'Textfsm file {tfsm_file} not found. Ignoring'
                            ' service'
                        )
                        continue

                    with open(tfsm_file, 'r') as f:
                        try:
                            tfsm_template = textfsm.TextFSM(f)
                            subelem['textfsm'] = tfsm_template
                        except Exception:  # pylint: disable=broad-except
                            logger.exception(
                                'Unable to load TextFSM file '
                                f'{tfsm_file} for service '
                                f"{svc_def['service']}")
                            continue
