from typing import TypeVar, Dict, Callable, List
from abc import abstractmethod
from collections import defaultdict
import time
from datetime import datetime, timezone
import logging
import random
from http import HTTPStatus
import json
import re
import operator
from urllib.parse import urlparse
import asyncio
from asyncio.subprocess import PIPE, DEVNULL
# pylint: disable=redefined-builtin
from concurrent.futures._base import TimeoutError
from contextlib import asynccontextmanager

from packaging import version as version_parse
import xmltodict
import asyncssh
import aiohttp
from dateparser import parse


from suzieq.poller.worker.services.service import RsltToken
from suzieq.shared.utils import get_timestamp_from_junos_time, known_devtypes
from suzieq.shared.exceptions import SqPollerConfError, UnknownDevtypeError

logger = logging.getLogger(__name__)
IOS_SLEEP_BET_CMDS = 5          # in seconds
TNode = TypeVar('TNode', bound='Node')


# pylint: disable=broad-except, attribute-defined-outside-init
class Node:
    '''Class defining communicating with a device for telemetry

    The device class provides most of the basic functionality necessary to
    communicate with a device. In this base class, we don't know the device
    type i.e. whether the device is a device running EOS, IOSXE etc. Once this
    info is known, the class of the device switches from this base class to
    the device-specific class such as EosNode, IosXENode etc. Every such
    device-specific class has its own specific function for fetching the data
    that'll help determine what commands to issue to a device given its
    version, type etc.

    A device type is either determined automatically (if we use SSH transport)
    or is specified by the user (mandatory for any other transport).

    A device is using this base class then only when it doesn't know its
    device type. So, till the device type is known, we keep invoking the
    method _detect_node_type, backing off every so often. If the device is
    an unsupported device, we do mark it as "unknown" to avoid re-initing
    the info constantly.

    To reduce the overhead of setting up an SSH connection everytime we want
    to communicate, we use persistent SSH sessions to the extent possible. In
    some cases, creating this persistent session is not so easy. This is true
    for IOS devices, and so the device-specific class for those cases handle
    this in their own way. Any transport but SSH does not support persistence.

    Its possible when a device comes back up after a reboot, the device's info
    has changed such as its version. We'll need to re-init this data in order
    to continue fetching data from a device correctly in such a case. This is
    easy to do in case of SSH as the persistent connection is torn down when
    the device reboots. We don't have a good way to handle this with any other
    transport because they don;t have a persistent connection.

    The caller of this class MUST follow the following flow:
        * Create the class
        * Call initialize with the kwargs of at least the IP address of device,
          username, password (or keyfile)
        * Call run to start the node's polling
        * Call post_commands to request node to execute commands on device &
          return data. You'll need to supply a callback fn to call after the
          data is available.
    '''

    # pylint: disable=too-many-statements
    async def initialize(self, **kwargs) -> TNode:
        '''Since the class is largely async, we need a diff init'''

        if not kwargs:
            raise ValueError

        self.devtype = None  # Device type
        self.pvtkey_file = ""     # SSH private keyfile
        self.prev_result = {}  # No updates if nothing changed
        self.nsname = None
        self.svc_cmd_mapping = defaultdict(lambda: {})  # Not used yet
        self.logger = logging.getLogger(__name__)
        self.port = 0
        self.backoff = 15  # secs to backoff
        self.init_again_at = 0  # after this epoch secs, try init again
        self.connect_timeout = kwargs.get('connect_timeout', 15)
        self.cmd_timeout = 10  # default command timeout in seconds
        self.bootupTimestamp = 0
        self.version = "all"   # OS Version to pick the right defn
        self._service_queue = None
        self._conn = None
        self._tunnel = None
        self._session = None    # Used only by PANOS as of this comment
        self.svcs_proc = set()
        self.error_svcs_proc = set()
        self.ssh_ready = asyncio.Lock()
        self._last_exception = None
        self._exception_timestamp = None
        self._current_exception = None
        self.api_key = None
        self._stdin = self._stdout = self._long_proc = None
        self._max_retries_on_auth_fail = (kwargs.get('retries_on_auth_fail')
                                          or 0) + 1
        self._retry = self._max_retries_on_auth_fail
        self._discovery_lock = asyncio.Lock()
        self._cmd_sem = kwargs.get('cmd_sem', None)
        self._cmd_mutex = kwargs.get('cmd_mutex', None)
        self._cmd_pacer_sleep = kwargs.get('cmd_pacer_sleep', None)
        self.per_cmd_auth = kwargs.get('per_cmd_auth', True)

        self.address = kwargs["address"]
        self.hostname = kwargs["address"]  # default till we get hostname
        self.username = kwargs.get("username", "vagrant") or "vagrant"
        self.password = kwargs.get("password", "vagrant") or "vagrant"
        self.transport = kwargs.get("transport", "ssh")
        self.nsname = kwargs.get("namespace", "default")
        self.port = kwargs.get("port", 0)
        self.devtype = None
        self.ssh_config_file = kwargs.get("ssh_config_file", None)
        self.enable_password = kwargs.get('enable_password')

        passphrase = kwargs.get("passphrase", None)
        jump_host = kwargs.get("jump_host", "")
        if jump_host:
            jump_result = urlparse(jump_host)
            self.jump_user = jump_result.username or self.username
            self.jump_host = jump_result.hostname
            self.jump_host_key = None
            if jump_result.port:
                self.jump_port = jump_result.port
            else:
                self.jump_port = 22
            pvtkey_file = kwargs.pop('jump_host_key_file')
            if pvtkey_file:
                self.jump_host_key = self._decrypt_pvtkey(pvtkey_file,
                                                          passphrase)
                if not self.jump_host_key:
                    raise SqPollerConfError('Unable to read private key file'
                                            f' at {pvtkey_file}')
        else:
            self.jump_host = None
            self.jump_host_key = None

        self.ignore_known_hosts = kwargs.get('ignore_known_hosts', False)
        self.slow_host = kwargs.get('slow_host', False)
        # Number of commands to issue in parallel
        if self._cmd_sem:
            # Limit the num of parallel cmds we can issue when we have limits
            self.batch_size = 1
        else:
            # 4 is a number we picked to limit using up too many SSH sessions
            # Many newer implementations allow upto 5 simultaneous SSH sessions
            self.batch_size = 4
        pvtkey_file = kwargs.get("ssh_keyfile", None)
        if pvtkey_file:
            self.pvtkey = self._decrypt_pvtkey(pvtkey_file, passphrase)
            if not self.pvtkey:
                self.logger.error("ERROR: Falling back to password for "
                                  f"{self.address}:{self.port}")
                self.pvtkey = None
        else:
            self.pvtkey = None

        self._init_service_queue()

        devtype = kwargs.get("devtype", None)
        if devtype:
            self._set_devtype(devtype, '')
            self.logger.warning(
                f'{devtype} supplied for {self.address}:{self.port}')

        if self.transport == "ssh":
            self.port = self.port or 22
            await self._init_ssh(init_dev_data=False)
        elif self.transport == "https":
            self.port = self.port or 443
            if self.devtype:
                # Checking devtype to ensure we didn't get a REST transport
                # without also providing the device type.
                await self._init_rest()

        if not devtype:
            if self.transport != 'ssh':
                self.logger.error(
                    'devtype MUST be specified in inventory file if transport'
                    f'is not ssh for {self.address}')
                return self
            elif self.is_connected:
                # So we have a connection, lets figure out if we know what
                # to do with this device
                await self._detect_node_type()

        # Now we know the dev type, fetch the data we need about the
        # device to get cracking
        if not self.devtype and self._retry:
            # Unable to connect to the node, schedule later another attempt
            self._schedule_discovery_attempt()
        elif self.devtype not in ['unsupported', None] and self._retry:
            # OK, we know the devtype, now initialize the info we need
            # to start proper operation

            # IOS* closes the connection after the initial cmds
            # are executed. So close the conn at our end too
            # avoiding the initial persistent connection failure that
            # otherwise happens
            if self.devtype in ['iosxe', 'ios', 'iosxr']:
                await self._close_connection()

            await self._fetch_init_dev_data()
            if not self.hostname:
                self.hostname = self.address

        return self

    @property
    def last_exception(self) -> Exception:
        '''Last exception that occurred on this device'''
        return self._last_exception

    @property
    def current_exception(self) -> Exception:
        '''The current exception faced on this device'''
        return self._current_exception

    @current_exception.setter
    def current_exception(self, val: Exception):
        '''current exception setter'''
        self._last_exception = self._current_exception
        self._current_exception = val
        if val:
            self._exception_timestamp = int(time.time()*1000)

    @property
    def is_connected(self):
        '''Is there connectivity to the device at the transport level'''
        return self._conn is not None

    @asynccontextmanager
    async def cmd_pacer(self, use_sem: bool = True):
        '''Context Manager to implement throttling of commands.

        In many networks, backend authentication servers such as TACACS which
        handle authentication of logins and even command execution, cannot
        large volumes of authentication requests. Thanks to our use of
        asyncio, we can easily sends hundreds of connection requests to such
        servers, which effectively turns into authentication failures. To
        handle this, we add a user-specified maximum of rate of cmds/sec
        that the authentication can handle, and we pace it out. This code
        implements that pacer.

        Some networks communicate with a backend authentication server only
        on login while others contact it for authorization of a command as
        well. Its to handle this difference that we pass use_sem. Users set
        the per_cmd_auth to True if authorization is used. The caller of this
        function sets the use_sem apppropriately depending on when the context
        is invoked.

        Args:
          use_sem(bool): True if you want to use the pacer
        '''
        if self._cmd_sem and use_sem:
            async with self._cmd_sem:
                async with self._cmd_mutex:
                    await asyncio.sleep(self._cmd_pacer_sleep)
                yield
        else:
            yield

    def _decrypt_pvtkey(self, pvtkey_file: str, passphrase: str) -> str:
        """Decrypt private key file"""

        keydata: str = None
        if pvtkey_file:
            try:
                keydata = asyncssh.public_key.read_private_key(pvtkey_file,
                                                               passphrase)
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(
                    f"ERROR: Unable to read private key file {pvtkey_file}"
                    f"for jump host due to {e}")

        return keydata

    def _init_service_queue(self):
        if not self._service_queue:
            self._service_queue = asyncio.Queue()

    async def _close_connection(self):
        if self.is_connected:
            self._conn.close()
            await self._conn.wait_closed()
        if self._tunnel:
            self._tunnel.close()
            await self._tunnel.wait_closed()

        self._conn = None
        self._tunnel = None
        self._stdin = self._stdout = self._stderr = None

    async def _terminate(self):
        self.logger.warning(
            f'Node: {self.hostname} received signal to terminate')
        await self._close_connection()
        return

    def _create_error(self, cmd) -> dict:
        data = {'error': str(self.current_exception)}
        if isinstance(self.current_exception, TimeoutError):
            status = HTTPStatus.REQUEST_TIMEOUT
        elif isinstance(self.current_exception, asyncssh.misc.ProtocolError):
            status = HTTPStatus.FORBIDDEN
        elif isinstance(self.current_exception,
                        asyncssh.misc.PermissionDenied):
            status = HTTPStatus.FORBIDDEN
        elif hasattr(self.current_exception, 'code'):
            status = self.current_exception.code
        else:
            status = -1
        return self._create_result(cmd, status, data)

    def _create_result(self, cmd, status, data) -> dict:
        if self.port in [22, 443]:
            # Ignore port if defaults (SSH or HTTPS)
            addrstr = self.address
        else:
            addrstr = f'{self.address}:{self.port}'
        result = {
            "status": status,
            "timestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
            "cmd": cmd,
            "devtype": self.devtype,
            "namespace": self.nsname,
            "hostname": self.hostname,
            "address": addrstr,
            "version": self.version,
            "data": data,
        }
        return result

    async def _parse_device_type_hostname(self, output, _) -> None:
        devtype = ""
        hostname = None

        if output[0]["status"] == 0:
            # don't keep trying if we're connected to an unsupported dev
            devtype = 'unsupported'
            data = output[0]["data"]
            version_str = data

            if 'Arista' in data or 'vEOS' in data:
                devtype = "eos"
            elif "JUNOS " in data:
                model = re.search(r'Model:\s+(\S+)', data)
                if model:
                    if model.group(1).startswith(('mx', 'vmx')):
                        devtype = 'junos-mx'
                    elif 'qfx10' in model.group(1):
                        devtype = 'junos-qfx10k'
                    elif 'qfx' in model.group(1):
                        devtype = 'junos-qfx'
                    elif 'ex' in model.group(1):
                        devtype = 'junos-ex'
                    elif model.group(1).startswith(('srx', 'vSRX')):
                        devtype = 'junos-es'
                if not devtype:
                    devtype = "junos"
            elif "NX-OS" in data:
                devtype = "nxos"
            elif "SONiC" in data:
                devtype = "sonic"
            elif "Cisco IOS XR" in data:
                devtype = "iosxr"
            elif any(x in data for x in ["Cisco IOS XE", "Cisco IOS-XE"]):
                devtype = "iosxe"
            elif "Cisco IOS Software" in data:
                devtype = "ios"
            else:
                self.logger.info(
                    f'{self.address}: Got unrecognized device show version: '
                    f'{data}')

            if devtype.startswith("junos"):
                hmatch = re.search(r'Hostname:\s+(\S+)\n', data)
                if hmatch:
                    hostname = hmatch.group(1)
            elif devtype == "nxos":
                hgrp = re.search(r'[Dd]evice\s+name:\s+(\S+)', data)
                if hgrp:
                    hostname = hgrp.group(1)
                else:
                    hostname = self.address
            elif devtype == "eos":
                # We'll fill in the hostname when the node gets re-init
                hostname = None
            elif devtype in ["iosxe", "ios"]:
                matchval = re.search(r'(\S+)\s+uptime', output[0]['data'])
                if matchval:
                    hostname = matchval.group(1).strip()
                else:
                    hostname = self.address
            elif devtype != "iosxr":
                hgrp = re.search(r'(\S+)\s+uptime\s+is', data)
                if hgrp:
                    hostname = hgrp.group(1)
                else:
                    hostname = self.address

        elif (len(output) > 1) and (output[1]["status"] == 0):
            devtype = 'unsupported'
            data = output[1]["data"]
            if data:
                if "Cumulus Linux" in data:
                    devtype = "cumulus"
                else:
                    devtype = "linux"

                version_str = data
                # Hostname is the last line of the output
                if len(data.strip()) > 0:
                    hostname = data.splitlines()[-1].strip()

        if devtype == 'unsupported':
            if not self.current_exception:
                self.logger.info(
                    f'Unable to determine devtype for '
                    f'{self.address}:{self.port}')
                self._set_devtype(devtype, version_str)
                self._set_hostname(self.address)
                await self._close_connection()
                self.current_exception = UnknownDevtypeError()
        elif devtype:
            self.logger.warning(
                f'Detected {devtype} for {self.address}:{self.port},'
                f' {hostname}')
            self._set_devtype(devtype, version_str)
            self._set_hostname(hostname)
            self.current_exception = None

    async def _detect_node_type(self):
        '''Figure out what type of device this is: EOS, NXOS etc.

        Its only available if we're using ssh as transport
        '''

        devtype = None
        hostname = None

        if self.transport in ['ssh', 'local']:
            try:
                await self._get_device_type_hostname()
                # The above fn calls results in invoking a callback fn
                # that sets the device type
                devtype = self.devtype
            except Exception:
                self.logger.exception(f'{self.address}:{self.port}: Node '
                                      'discovery failed due to exception')
                # All the exceptions related to timeouts and authentication
                # problems are already catched inside. If we get an
                # exception here, this is unexpected and most likely something
                # went wrong with the command output parsing.
                # In this case there is not point in retrying discovery, it is
                # likely a bug.
                self._retry = 0
                devtype = None

            if not devtype:
                self.logger.debug(
                    f'No devtype for {self.hostname} {self.current_exception}')
                # We were not able to do the discovery, schedule a new attempt
                self._schedule_discovery_attempt()
                return
            else:
                self._set_devtype(devtype, '')
                self._set_hostname(hostname)
        else:
            self.logger.error(
                f'Non-SSH transport node {self.address}:{self.port} '
                'has no devtype specified. Node will not be polled')

    async def _get_device_type_hostname(self):
        """Determine the type of device we are talking to if using ssh/local"""
        # There isn't that much of a difference in running two commands versus
        # running them one after the other as this involves an additional ssh
        # setup time. show version works on most networking boxes and
        # hostnamectl on Linux systems. That's all we support today.
        await self._exec_cmd(self._parse_device_type_hostname,
                             ["show version",
                              "cat /etc/os-release && hostname"],
                             None, 'text', only_one=True)

    def _set_devtype(self, devtype: str, version_str: str) -> None:
        """Change the class based on the device type"""

        if not devtype:
            return

        if devtype == 'unsupported':
            self.devtype = devtype
            return

        if devtype not in known_devtypes():
            self.logger.error(f'An unknown devtype {devtype} is being added.'
                              f' This will cause problems. '
                              f'Node {self.address}:{self.port}')
            raise ValueError

        if self.devtype != devtype:
            self.devtype = devtype
            if self.devtype == "cumulus":
                self.__class__ = CumulusNode
            elif self.devtype == "eos":
                self.__class__ = EosNode
            elif self.devtype == "iosxe":
                self.__class__ = IosXENode
            elif self.devtype == "iosxr":
                self.__class__ = IosXRNode
            elif self.devtype == "ios":
                self.__class__ = IOSNode
            elif self.devtype.startswith("junos"):
                self.__class__ = JunosNode
            elif self.devtype == "nxos":
                self.__class__ = NxosNode
            elif self.devtype.startswith("sonic"):
                self.__class__ = SonicNode
            elif self.devtype == "panos":
                self.__class__ = PanosNode
            elif self.devtype == "linux":
                self.__class__ = LinuxNode

        # Now invoke the class specific NOS version extraction
        if version_str:
            self._extract_nos_version(version_str)

    def _set_hostname(self, hostname=None):
        '''Set node hostname'''
        if hostname:
            self.hostname = hostname

    async def _init_jump_host_connection(
            self,
            options: asyncssh.SSHClientConnectionOptions) -> None:
        """Initialize jump host connection if necessary

        Args:
            options (asyncssh.SSHClientConnectionOptions): non-jump host opt
        """

        if self._tunnel:
            return

        if self.jump_host_key:
            jump_host_options = asyncssh.SSHClientConnectionOptions(
                client_keys=self.jump_host_key,
                connect_timeout=self.connect_timeout,
            )

            if self.ignore_known_hosts:
                jump_host_options = asyncssh.SSHClientConnectionOptions(
                    options=jump_host_options,
                    known_hosts=None
                )
            if self.ssh_config_file:
                jump_host_options = asyncssh.SSHClientConnectionOptions(
                    options=jump_host_options,
                    config_file=[self.ssh_config_file]
                )
        else:
            jump_host_options = options

        try:
            if self.jump_host:
                self.logger.info(
                    'Using jump host: %s, with username: %s, and port: %s',
                    self.jump_host, self.jump_user, self.jump_port
                )
                self._tunnel = await asyncssh.connect(
                    self.jump_host, port=self.jump_port,
                    options=jump_host_options, username=self.jump_user)
                self.logger.info(
                    'Connection to jump host %s succeeded', self.jump_host)

        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(
                f'Cannot connect to jump host: {self.jump_host} ({e})')
            self.current_exception = e
            self._conn = None
            self._tunnel = None

    def _init_ssh_options(self) -> asyncssh.SSHClientConnectionOptions:
        """Build out the asycnssh options as specified by user config

        This is a routine because its used in multiple places.
        Returns:
            asyncssh.SSHClientConnectionOptions: [description]
        """
        options = asyncssh.SSHClientConnectionOptions(
            connect_timeout=self.connect_timeout,
            username=self.username,
            agent_identities=self.pvtkey if self.pvtkey else None,
            client_keys=self.pvtkey if self.pvtkey else None,
            password=self.password if not self.pvtkey else None,
            kex_algs='+diffie-hellman-group1-sha1',  # for older boxes
            encryption_algs='+aes256-cbc',           # for older boxes
        )
        if self.ignore_known_hosts:
            options = asyncssh.SSHClientConnectionOptions(
                options=options,
                known_hosts=None,
            )
        if self.ssh_config_file:
            options = asyncssh.SSHClientConnectionOptions(
                options=options,
                config=[self.ssh_config_file],
            )

        return options

    async def _init_ssh(self, init_dev_data=True, use_lock=True) -> None:
        '''Setup a persistent SSH connection to our node.

        In some cases such as IOSXE/XR, this may not actually setup a
        persistent SSH session, but does the basics of setting one up.

        use_lock is a critical parameter to avoid deadlocks. If too
        many services attempt to init_ssh at the same time, we'll cause
        much heartache. So, we acquire a lock to ensure this is done only
        once.

        However, when the calling party has additional work to do, the
        caller MUST acquire the lock and pass use_lock=False. And the
        caller MUST ensure they release the lock.
        '''
        if self._retry and not self._conn:
            if use_lock:
                await self.ssh_ready.acquire()

            # Someone else may have already succeeded in getting the SSH conn
            if self.is_connected or not self._retry:
                if use_lock:
                    self.ssh_ready.release()
                return

            options = self._init_ssh_options()
            if self.jump_host and not self._tunnel:
                await self._init_jump_host_connection(options)
                if not self._tunnel:
                    if use_lock:
                        self.ssh_ready.release()
                    return

            async with self.cmd_pacer():
                try:
                    if self._tunnel:
                        self._conn = await self._tunnel.connect_ssh(
                            self.address, port=self.port,
                            username=self.username,
                            options=options)
                    else:
                        self._conn = await asyncssh.connect(
                            self.address,
                            username=self.username,
                            port=self.port,
                            options=options)
                    self.logger.info(
                        f"Connected to {self.address}:{self.port} at "
                        f"{time.time()}")
                    # Reset authentication fail attempt on success
                    self._retry = self._max_retries_on_auth_fail
                except Exception as e:  # pylint: disable=broad-except
                    if isinstance(e, asyncssh.HostKeyNotVerifiable):
                        self.logger.error(
                            f'Unable to connect to {self.address}: {self.port}'
                            ', host key is unknown. If you do not need to '
                            ' verify the host identity, add '
                            '"ignore-known-hosts: True" in the device section '
                            'of the inventory')
                    elif isinstance(e, asyncssh.misc.PermissionDenied):
                        self.logger.error(
                            f'Authentication failed to {self.address}. '
                            'Not retrying to avoid locking out user. Please '
                            'restart poller with proper authentication')
                        self._retry -= 1
                    else:
                        self.logger.error('Unable to connect to '
                                          f'{self.address}:{self.port}, {e}')
                    self.current_exception = e
                    await self._close_connection()
                    self._conn = None
                finally:
                    if use_lock:
                        self.ssh_ready.release()

            # Release here because init_dev_data uses this lock as well
            # We need to be sure that devtype is set, otherwise the
            # _fetch_dev_data function is not implemented and will raise.
            if init_dev_data and self.devtype:
                await self._fetch_init_dev_data()

    @abstractmethod
    async def _init_rest(self):
        '''Check that connectivity exists and works'''
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    # pylint: disable=unused-argument
    async def _local_gather(self, service_callback: Callable,
                            cmd_list: List[str], cb_token: RsltToken,
                            oformat: str, timeout: int):
        """Use local command execution to execute the commands requested

        This function takes the raw list of commands to execute on the device
        locally and calls the callback function with the data returned.

        Args:
            service_callback: The callback fn to call when we have the data
                for the commands requested (or error for any given command)
            cmd_list: The list of commands to be executed on the remote device
            cb_token: The callback token to be returned to the callback fn
            oformat: The output format we're expecting the data in: text, json
                or mixed
            timeout: How long to wait for the commands to complete, in secs
            only_one: Run till the first command in the list succeeds and
                then return
        """
        result = []
        for cmd in cmd_list:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=PIPE,
                                                         stderr=PIPE)

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.cmd_timeout)

                if not proc.returncode:
                    d = stdout.decode('ascii', 'ignore')
                    result.append(self._create_result(
                        cmd, proc.returncode, d))
                else:
                    d = stderr('ascii', 'ignore')
                    result.append(self._create_error(cmd))

            except asyncio.TimeoutError as e:
                self.current_exception = e
                result.append(self._create_error(cmd))

        await service_callback(result, cb_token)

    def _schedule_discovery_attempt(self):
        """Schedule a new attempt for the node discovery
        """
        # Add an additional offset to avoid all the nodes retry all together
        offset = (random.randint(0, 1000) / 1000)
        self.backoff = min(600, self.backoff * 2) + offset
        self.init_again_at = time.time() + self.backoff

        next_time = datetime.fromtimestamp(self.init_again_at)
        logger.info(
            f'Discovery of {self.address}:{self.port} will be retried '
            f'from {next_time}'
        )

    # pylint: disable=unused-argument
    async def _ssh_gather(self, service_callback: Callable,
                          cmd_list: List[str], cb_token: RsltToken,
                          oformat: str, timeout: int, only_one: bool = False):
        """Use SSH to execute the commands requested

        This function takes the raw list of commands to execute on the device
        via SSH and calls the callback function with the data returned.

        Args:
            service_callback: The callback fn to call when we have the data
                for the commands requested (or error for any given command)
            cmd_list: The list of commands to be executed on the remote device
            cb_token: The callback token to be returned to the callback fn
            oformat: The output format we're expecting the data in: text, json
                or mixed
            timeout: How long to wait for the commands to complete, in secs
            only_one: Run till the first command in the list succeeds and
                then return
        """
        result = []

        if cmd_list is None:
            await service_callback(result, cb_token)

        if not self._conn:
            await self._init_ssh()
            if not self._conn:
                for cmd in cmd_list:
                    self.logger.error(
                        "Unable to connect to node %s cmd %s",
                        self.hostname, cmd)
                    result.append(self._create_error(cmd))
                await service_callback(result, cb_token)
                return

        if isinstance(cb_token, RsltToken):
            cb_token.node_token = self.bootupTimestamp

        timeout = timeout or self.cmd_timeout
        async with self.cmd_pacer(self.per_cmd_auth):
            for cmd in cmd_list:
                try:
                    output = await asyncio.wait_for(self._conn.run(cmd),
                                                    timeout=timeout)
                    if self.current_exception:
                        self.logger.info(
                            '%s recovered from previous exception',
                            self.hostname)
                        self.current_exception = None
                    result.append(self._create_result(
                        cmd, output.exit_status, output.stdout))
                    if (output.exit_status == 0) and only_one:
                        break
                except Exception as e:
                    self.current_exception = e
                    result.append(self._create_error(cmd))
                    if not isinstance(e, asyncio.TimeoutError):
                        self.logger.error(
                            "%s output for %s failed due to %s", cmd,
                            self.hostname, e)
                        await self._close_connection()
                    else:
                        self.logger.error(
                            "%s output for %s failed due to timeout", cmd,
                            self.hostname)

                    break

        await service_callback(result, cb_token)

    async def _exec_cmd(self, service_callback, cmd_list, cb_token,
                        oformat='json', timeout=None, only_one=False,
                        reconnect=True):
        '''Routine to execute a given set of commands on device

        if only_one is True, commands are executed until the first one that
        succeeds, and the rest are ignored.
        '''
        if self.transport == "ssh":
            await self._ssh_gather(service_callback, cmd_list, cb_token,
                                   oformat, timeout, only_one)
        elif self.transport == "https":
            await self._rest_gather(service_callback, cmd_list,
                                    cb_token, oformat, timeout)
        elif self.transport == "local":
            await self._local_gather(service_callback, cmd_list,
                                     cb_token, oformat, timeout)
        else:
            self.logger.error(
                "Unsupported transport %s for node %s",
                self.transport, self.hostname)
        return

    # pylint: disable=too-many-nested-blocks
    async def _exec_service(self, service_callback, svc_defn: dict,
                            cb_token: RsltToken):
        '''Routine that determines cmdlist to be executed for given service

        And invokes appropriate transport routine to execute the cmds and
        return the data to the service that requested it.
        '''
        result = []  # same type as gather function
        cmd = None
        if not svc_defn:
            return result

        if (not self.devtype and self._retry
                and self.init_again_at < time.time()):
            # When we issue bunch of commands multiple tasks might try to
            # perform the discovery all together, we need only one of them
            # trying to perform the discovery, all the others can fail
            if not self._discovery_lock.locked():
                async with self._discovery_lock:
                    await self._detect_node_type()

        if not self.devtype:
            result.append(self._create_error(svc_defn.get("service", "-")))
            return await service_callback(result, cb_token)

        if self.devtype == 'unsupported':
            # Service code 418 means I'm a teapot in http status codes
            # in other words, I won't brew coffee because I'm a teapot
            result.append(self._create_result(
                svc_defn, 418, "No service definition"))
            self.error_svcs_proc.add(svc_defn.get("service"))
            return await service_callback(result, cb_token)

        # Update our boot time value into the callback token
        if cb_token:
            cb_token.bootupTimestamp = self.bootupTimestamp

        self.svcs_proc.add(svc_defn.get("service"))
        use = svc_defn.get(self.hostname, None)
        if not use:
            use = svc_defn.get(self.devtype, {})
        if not use:
            if svc_defn.get("service") not in self.error_svcs_proc:
                result.append(self._create_result(
                    svc_defn, HTTPStatus.NOT_FOUND, "No service definition"))
                self.error_svcs_proc.add(svc_defn.get("service"))
            return await service_callback(result, cb_token)

        # TODO This kind of logic should be encoded in config and node
        # shouldn't have to know about it
        if "copy" in use:
            use = svc_defn.get(use.get("copy"))

        if use:
            if isinstance(use, list):
                # There's more than one version here, we have to pick ours
                for item in use:
                    if item['version'] != "all":
                        os_version = item['version']
                        opdict = {'>': operator.gt, '<': operator.lt,
                                  '>=': operator.ge, '<=': operator.le,
                                  '=': operator.eq, '!=': operator.ne}
                        op = operator.eq

                        for elem, val in opdict.items():
                            if os_version.startswith(elem):
                                os_version = os_version.replace(
                                    elem, '').strip()
                                op = val
                                break

                        if op(version_parse.LegacyVersion(self.version),
                                version_parse.LegacyVersion(os_version)):
                            cmd = item.get('command', None)
                            use = item
                            break
                    else:
                        cmd = item.get("command", None)
                        use = item
                        break
            else:
                cmd = use.get("command", None)

        if not cmd:
            result.append(self._create_result(
                svc_defn, HTTPStatus.NOT_FOUND, "No service definition"))
            self.error_svcs_proc.add(svc_defn.get("service"))
            return await service_callback(result, cb_token)

        oformat = use.get('format', 'json')
        if not isinstance(cmd, list):
            if use.get('textfsm'):
                oformat = 'text'
            cmdlist = [cmd]
        else:
            # TODO: Handling format for the multiple cmd case
            cmdlist = [x.get('command', '') for x in cmd]

        await self._exec_cmd(service_callback, cmdlist, cb_token,
                             oformat=oformat, timeout=cb_token.timeout)

    @abstractmethod
    async def _fetch_init_dev_data(self):
        """Start data fetch to initialize the class with specific device attrs

        This function initiates the process of fetching critical pieces
        of info about the device such as version, os type and hostname.
        The version string is specifically used to identify which command
        needs to be executed on a device.

        This is where the list of commands specific to the device for
        extracting the said info is specified.
        """
        raise NotImplementedError(
            f'{self.address}: initing base Node class')

    @abstractmethod
    async def _parse_init_dev_data(self, output: List,
                                   cb_token: RsltToken) -> None:
        """Parse the version, uptime and hostname info from the output

        This function is the callback that extracts the uptime and hostname
        from the data fetched from the device. This function calls the device
        specific version extraction function to extract the version.

        Args:
            output: The list of outputs, one per command specified
            cb_token: The callback token we passed to the data fetcher function
        """
        raise NotImplementedError(
            f'{self.address}: parsing init base Node class')

    @abstractmethod
    def _extract_nos_version(self, data: str) -> str:
        """Extract the version string from the output passed

        Args:
            data: The output of the command to search for the version
                string

        Returns:
            The version as a string
        """
        raise NotImplementedError(
            f'{self.address}: extracting NOS in init base Node class')

    @abstractmethod
    async def _rest_gather(self, service_callback: Callable,
                           cmd_list: List[str], cb_token: RsltToken,
                           oformat: str = "json", timeout: int = None):
        """Use HTTP(s) to execute the commands requested

        This function takes the raw list of commands to execute on the device
        via a REST API and calls the callback function with the data returned.

        Args:
            service_callback: The callback fn to call when we have the data
                for the commands requested (or error for any given command)
            cmd_list: The list of commands to be executed on the remote device
            cb_token: The callback token to be returned to the callback fn
            oformat: The output format we're expecting the data in: text, json
                or mixed
            timeout: How long to wait for the commands to complete, in secs
            only_one: Run till the first command in the list succeeds and
                then return
        """
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    def post_commands(self, service_callback: Callable, svc_defn: Dict,
                      cb_token: RsltToken):
        """Post commands to the device for servicing

        Whenever any user of a device wishes to issue a command to
        this device, they call this function with a list of commands
        to be executed, and a callback function that is invoked when
        the commands have been executed and either there's an error or
        data is returned. Multiple commands imply the result contains
        a list of responses, one for each command that was passed. The
        result itself is a dictionary which includes the command for
        which this is the result. If the user wishes to have a token
        returned to the callback function, they can pass that via the
        cb_token parameter.

        Args:
            service_callback: The callback function
            svc_defn: The service definition file from which the
                appropriate command will be extracted for the device
            cb_token: The callback token to be passed to the callback
                function
        """
        if cb_token:
            cb_token.nodeQsize = self._service_queue.qsize()
        self._service_queue.put_nowait([service_callback, svc_defn, cb_token])

    async def run(self):
        '''Main workhorse routine for Node

        Waits for services to be executed on node via service queue,
        and executes them.
        '''

        tasks = []
        try:
            while True:
                while len(tasks) < self.batch_size:

                    request = await self._service_queue.get()

                    if request:
                        tasks.append(self._exec_service(
                            request[0], request[1], request[2]))
                        self.logger.debug(
                            f"Scheduling {request[2].service} for execution")
                    if self._service_queue.empty():
                        break

                if tasks:
                    _, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED)

                    tasks = list(pending)
        except asyncio.CancelledError:
            await self._terminate()
            return


class EosNode(Node):
    '''EOS Node specific implementation'''

    async def _init_rest(self):
        '''Check that connectivity and authentication works'''

        timeout = self.cmd_timeout

        auth = aiohttp.BasicAuth(self.username,
                                 password=self.password or 'vagrant')
        url = f"https://{self.address}:{self.port}/command-api"

        try:
            async with aiohttp.ClientSession(
                    auth=auth, timeout=self.connect_timeout,
                    connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.post(url, timeout=timeout) as response:
                    _ = response.status
        except Exception as e:
            self.logger.error(
                f'Unable to connect to {self.address}:{self.port}, '
                f'error: {str(e)}')

    async def _fetch_init_dev_data(self):

        if self.transport == 'https':
            cmdlist = ["show version", "show hostname"]
        else:
            cmdlist = ["show version|json", "show hostname|json"]
        await self._exec_cmd(self._parse_init_dev_data, cmdlist,
                             None, reconnect=False)

    async def _ssh_gather(self, service_callback, cmd_list, cb_token, oformat,
                          timeout, only_one=False):
        """Use SSH to execute the commands requested

        This function takes the raw list of commands to execute on the device
        via SSH and calls the callback function with the data returned.

        Args:
            service_callback: The callback fn to call when we have the data
                for the commands requested (or error for any given command)
            cmd_list: The list of commands to be executed on the remote device
            cb_token: The callback token to be returned to the callback fn
            oformat: The output format we're expecting the data in: text, json
                or mixed
            timeout: How long to wait for the commands to complete, in secs
            only_one: Run till the first command in the list succeeds and
                then return
        """
        # We need to add the JSON option for all commands that support JSON
        # output since the command provided assumes REST API
        newcmd_list = []
        for cmd in cmd_list:
            if (oformat == "json") and not cmd.endswith('json'):
                cmd += '| json'

            newcmd_list.append(cmd)

        return await super()._ssh_gather(service_callback, newcmd_list,
                                         cb_token, oformat, timeout, only_one)

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat="json", timeout=None):

        result = []
        if not cmd_list:
            return result

        timeout = timeout or self.cmd_timeout

        now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        auth = aiohttp.BasicAuth(self.username,
                                 password=self.password or 'vagrant')
        data = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "id": int(now),
            "params": {"version": 1, "format": oformat, "cmds": cmd_list},
        }
        headers = {"Content-Type": "application/json"}
        if self.port:
            url = "https://{}:{}/command-api".format(self.address, self.port)
        else:
            url = "https://{}:{}/command-api".format(self.address, self.port)

        output = []
        status = 200  # status OK

        async with self.cmd_pacer(self.per_cmd_auth):
            try:
                async with aiohttp.ClientSession(
                        auth=auth, conn_timeout=self.connect_timeout,
                        read_timeout=timeout,
                        connector=aiohttp.TCPConnector(ssl=False)) as session:
                    async with session.post(url, json=data,
                                            timeout=timeout,
                                            headers=headers) as response:
                        status = response.status
                        if status == HTTPStatus.OK:
                            json_out = await response.json()
                            if "result" in json_out:
                                output.extend(json_out["result"])
                            else:
                                output.extend(
                                    json_out["error"].get('data', []))

                            for i, cmd in enumerate(cmd_list):
                                result.append(
                                    {
                                        "status": status,
                                        "timestamp": now,
                                        "cmd": cmd,
                                        "devtype": self.devtype,
                                        "namespace": self.nsname,
                                        "hostname": self.hostname,
                                        "address": self.address,
                                        "data":
                                        output[i]
                                        if isinstance(output, list)
                                        else output,
                                    }
                                )
                        else:
                            for cmd in cmd_list:
                                result.append(self._create_error(cmd))
                            self.logger.error(
                                f'{self.transport}://{self.hostname}:'
                                f'{self.port}: Commands failed due to '
                                f'{response.status}')
            except Exception as e:
                self.current_exception = e
                for cmd in cmd_list:
                    result.append(self._create_error(cmd))
                self.logger.error(
                    f"{self.transport}://{self.hostname}:{self.port}: Unable "
                    f"to communicate with node due to {str(e)}")

        await service_callback(result, cb_token)

    async def _parse_init_dev_data(self, output, cb_token) -> None:

        if output[0]["status"] == 0 or output[0]["status"] == 200:
            if self.transport == 'ssh':
                try:
                    data = json.loads(output[0]["data"])
                except json.JSONDecodeError:
                    self.logger.error(
                        f'nodeinit: Error decoding JSON for '
                        f'{self.address}:{self.port}')
                    return
            else:
                data = output[0]["data"]
            self.bootupTimestamp = data["bootupTimestamp"]
            self._extract_nos_version(data)
            if not self.version:
                self.logger.error(f'nodeinit: Error getting version for '
                                  f'{self.address}: {self.port}')

        if (len(output) > 1) and (output[1]["status"] in [0, 200]):
            if self.transport == 'ssh':
                try:
                    data = json.loads(output[1]["data"])
                except json.JSONDecodeError:
                    self.logger.error(
                        f'nodeinit: Error decoding JSON for '
                        f'{self.address}:{self.port}')
                    return
            else:
                data = output[1]["data"]
            self.hostname = data["fqdn"]

    def _extract_nos_version(self, data) -> None:
        # < 4.27 or so, the cases were different.
        if isinstance(data, str):
            match = re.search(r'Software Image Version:\s+(\S+)', data,
                              re.IGNORECASE)
            if match:
                self.version = match.group(1).strip()
            else:
                self.logger.warning(
                    f'Cannot parse version from {self.address}:{self.port}')
                self.version = "all"
        else:
            self.version = data['version']


class CumulusNode(Node):
    '''Cumulus Node specific implementation'''

    async def _fetch_init_dev_data(self):
        """Fill in the boot time of the node by executing certain cmds"""
        await self._exec_cmd(self._parse_init_dev_data,
                             ["cat /proc/uptime", "hostname",
                              "cat /etc/os-release"], None, 'text')

    async def _parse_init_dev_data(self, output, _) -> None:
        """Parse the uptime command output"""

        if output[0]["status"] == 0:
            upsecs = output[0]["data"].split()[0]
            self.bootupTimestamp = int(int(time.time()*1000)
                                       - float(upsecs)*1000)
        if (len(output) > 1) and (output[1]["status"] == 0):
            data = output[1].get("data", '')
            hostname = data.splitlines()[0].strip()
            self.hostname = hostname

        if (len(output) > 2) and (output[2]["status"] == 0):
            data = output[2].get("data", '')
            self._extract_nos_version(data)

    def _extract_nos_version(self, data: str) -> None:
        """Extract the version from the output of /etc/os-release

        Args:
            data (str): output of show version

        Returns:
            str: version
        """
        version_str = re.search(r'VERSION_ID=(\S+)', data)
        if version_str:
            self.version = version_str.group(1).strip()
        else:
            self.version = "all"
            self.logger.error(
                f'Cannot parse version from {self.address}:{self.port}')

    async def _init_rest(self):
        '''Check that connectivity exists and works'''

        auth = aiohttp.BasicAuth(self.username, password=self.password)
        url = "https://{0}:{1}/nclu/v1/rpc".format(self.address, self.port)
        headers = {"Content-Type": "application/json"}

        async with self.cmd_pacer(self.per_cmd_auth):
            try:
                async with aiohttp.ClientSession(
                        auth=auth, timeout=self.cmd_timeout,
                        connector=aiohttp.TCPConnector(ssl=False),
                ) as session:
                    async with session.post(url, headers=headers) as response:
                        _ = response.status
            except Exception as e:
                self.current_exception = e
                self.logger.error(
                    f"{self.transport}://{self.hostname}:{self.port}: Unable "
                    f"to communicate with node due to {str(e)}")

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat='json', timeout=None):

        result = []
        if not cmd_list:
            return result

        auth = aiohttp.BasicAuth(self.username, password=self.password)
        url = "https://{0}:{1}/nclu/v1/rpc".format(self.address, self.port)
        headers = {"Content-Type": "application/json"}

        async with self.cmd_pacer(self.per_cmd_auth):
            try:
                async with aiohttp.ClientSession(
                        auth=auth,
                        timeout=timeout or self.cmd_timeout,
                        connector=aiohttp.TCPConnector(ssl=False),
                ) as session:
                    for cmd in cmd_list:
                        data = {"cmd": cmd}
                        async with session.post(
                                url, json=data, headers=headers
                        ) as response:
                            result.append({
                                "status": response.status,
                                "timestamp": int(datetime.now(tz=timezone.utc)
                                                 .timestamp() * 1000),
                                "cmd": cmd,
                                "devtype": self.devtype,
                                "namespace": self.nsname,
                                "hostname": self.hostname,
                                "address": self.address,
                                "data": await response.text(),
                            })
            except Exception as e:
                self.current_exception = e
                result.append(self._create_error(cmd_list))
                self.logger.error(
                    f"{self.transport}://{self.hostname}:{self.port}: Unable "
                    f"to communicate with node due to {str(e)}")

        await service_callback(result, cb_token)


class LinuxNode(CumulusNode):
    '''Linux server node'''


class IosXRNode(Node):
    '''IOSXR Node specific implementation'''

    async def _init_rest(self):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat='json', timeout=None):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _fetch_init_dev_data(self):
        """Fill in the boot time of the node by executing certain cmds"""
        await self._exec_cmd(self._parse_init_dev_data,
                             ["show version", "show run hostname"],
                             None, 'text')

    async def _init_ssh(self, init_dev_data=True,
                        use_lock: bool = True) -> None:
        '''Need to start a neverending process to keep persistent ssh

        IOS XR's ssh is fragile and archaic. It doesn't support sending
        multiple commands over a single SSH connection as most other devices
        do. I suspect this may not be the only one. The bug is mentioned in
        https://github.com/ronf/asyncssh/issues/241. To overcome this issue,
        we wait in a loop for things to succeed. There's no point in continuing
        if this doesn't succeed. Maybe better to abort after a fixed number
        of retries to enable things like run-once=gather to work.
        '''
        backoff_period = 1
        if use_lock:
            await self.ssh_ready.acquire()

        while not self._conn:

            if not self._retry:
                break

            await super()._init_ssh(init_dev_data=False, use_lock=False)

            if self.is_connected:
                break

            await asyncio.sleep(backoff_period)
            backoff_period *= 2
            backoff_period = min(backoff_period, 120)

        if self.is_connected and not self._long_proc:
            try:
                self._long_proc = await self._conn.create_process(
                    'run tail -s 3600 -f /etc/version', stdout=DEVNULL,
                    stderr=DEVNULL)
                self.logger.info(
                    f'Persistent SSH present for {self.hostname}')
                if init_dev_data:
                    await self._fetch_init_dev_data()
            except Exception:
                self._conn = self._long_proc = None

        if use_lock:
            self.ssh_ready.release()

    async def _parse_init_dev_data(self, output, cb_token) -> None:
        '''Parse the version for uptime and hostname'''
        if output[0]["status"] == 0:
            data = output[0]['data']
            timestr = re.search(r'uptime is (.*)\n', data)
            if timestr:
                self.bootupTimestamp = int(datetime.utcfromtimestamp(
                    parse(timestr.group(1)).timestamp()).timestamp()*1000)
            else:
                self.logger.error(
                    f'Cannot parse uptime from {self.address}:{self.port}')
                self.bootupTimestamp = -1

            self._extract_nos_version(data)

        if (len(output) > 1) and (output[1]["status"] == 0):
            data = output[1]['data']
            hostname = re.search(r'hostname (\S+)', data.strip())
            if hostname:
                self.hostname = hostname.group(1)
                self.logger.error(f'set hostname of {self.address}:{self.port}'
                                  f' to {hostname.group(1)}')

    def _extract_nos_version(self, data) -> None:
        match = re.search(r'Version\s+:\s+ (\S+)', data)
        if match:
            self.version = match.group(1).strip()
        else:
            self.logger.warning(
                f'Cannot parse version from {self.address}:{self.port}')
            self.version = "all"


class IosXENode(Node):
    '''IOS-XE Node-sepcific telemetry gather implementation'''

    async def _init_rest(self):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat='json', timeout=None):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _fetch_init_dev_data(self):
        """Fill in the boot time of the node by executing certain cmds"""
        await self._exec_cmd(self._parse_init_dev_data,
                             ["show version"], None, 'text')

    async def _init_ssh(self, init_dev_data=True,
                        use_lock: bool = True) -> None:
        '''Need to start an interactive session for XE

        Many IOSXE devices cannot accept commands as fast as we can fire them.
        Furthermore, many TACACS servers also collapse under the load of
        multiple authemtication requests because each SSH session needs to be
        authenticated, not just the main SSH connection.
        '''
        backoff_period = 1
        self.WAITFOR = r'.*[>#]\s*$'

        self.logger.info(
            f'Trying to reconnect via SSH for {self.hostname}')

        if not self._retry or (self._conn and self._stdin):
            return

        if use_lock:
            await self.ssh_ready.acquire()

        while not self.is_connected:
            # Don't release rel lock here
            await super()._init_ssh(init_dev_data=False, use_lock=False)

            if self.is_connected:
                self.logger.info(
                    f'Reconnect succeeded via SSH for {self.hostname}')
                break

            if not self._retry:
                break

            await asyncio.sleep(backoff_period)
            backoff_period *= 2
            backoff_period = min(backoff_period, 120)

        if self.is_connected and not self._stdin:
            self.logger.info(
                f'Trying to create Persistent SSH for {self.hostname}')
            async with self.cmd_pacer(self.per_cmd_auth):
                try:
                    self._stdin, self._stdout, self._stderr = \
                        await self._conn.open_session(term_type='xterm')
                    self.logger.info(
                        f'Persistent SSH created for {self.hostname}')

                    output = await self.wait_for_prompt()
                    if output.strip().endswith('>'):
                        if await self._handle_privilege_escalation() == -1:
                            await self._close_connection()
                            self._conn = None
                            self._stdin = None
                            self._retry -= 1
                            if use_lock:
                                self.ssh_ready.release()
                            return
                    # Reset number of retries on successful auth
                    self._retry = self._max_retries_on_auth_fail
                except Exception as e:
                    if isinstance(e, asyncssh.misc.PermissionDenied):
                        self._retry -= 1
                    self.current_exception = e
                    self.logger.error('Unable to create persistent SSH session'
                                      f' for {self.hostname} due to {str(e)}')
                    self._conn = None
                    self._stdin = None
                    if use_lock:
                        self.ssh_ready.release()
                    return

                # Set the terminal length to 0 to avoid paging
                self._stdin.write('terminal length 0\n')
                output = await self._stdout.readuntil(self.WAITFOR)

            if init_dev_data:
                await self._fetch_init_dev_data()

        if use_lock:
            self.ssh_ready.release()
        return

    async def _handle_privilege_escalation(self) -> int:
        '''Escalata privilege if necessary

        Returns 0 on success, -1 otherwise'''

        self.logger.info(
            f'Privilege escalation required for {self.hostname}')
        self._stdin.write('enable\n')
        output = await self.wait_for_prompt(r'Password:\s*')
        if self.enable_password:
            self._stdin.write(self.enable_password + '\n')
        else:
            self._stdin.write(self.password + '\n')

        output = await self.wait_for_prompt()
        if (output in ['suzieq timeout', 'Password:'] or
                output.strip().endswith('>')):
            self.logger.error(
                f'Privilege escalation failed for {self.hostname}'
                ', Aborting connection')
            return -1

        self.logger.info(f'Privilege escalation succeeded for {self.hostname}')
        return 0

    async def wait_for_prompt(self, prompt: str = None,
                              timeout: int = 90) -> str:
        """Wait for specified prompt upto timeout duration

        Since we're waiting for a prompt, we want to not wait forever.
        asyncssh's readuntil doesn't take a timeout parameter as of
        2.9.0. So, instead of adding a asyncio.waitfor everywhere, we
        just call this routine. By default, we wait for 90s

        Args:
            prompt[str]: The prompt string to wait for
            timeout[int]: How long to wait in secs
        Returns:
            the output data or 'timeout'
        """
        if prompt is None:
            prompt = self.WAITFOR
        coro = self._stdout.readuntil(prompt)
        try:
            output = await asyncio.wait_for(coro, timeout=timeout)
            return output
        except asyncio.TimeoutError:
            self.current_exception = asyncio.TimeoutError
            self.logger.error(f'{self.address}.{self.port} '
                              'Timed out waiting for expected prompt')
            # Return something that won't ever be in real output
            return 'suzieq timeout'

    async def _parse_init_dev_data(self, output, cb_token) -> None:
        '''Parse the version for uptime and hostname'''
        if not isinstance(output, list):
            # In some errors, the output returned is not a list
            self.bootupTimestamp = -1
            return

        if output[0]["status"] == 0:
            data = output[0]['data']
            hostupstr = re.search(r'(\S+)\s+uptime is (.*)\n', data)
            if hostupstr:
                self._set_hostname(hostupstr.group(1))
                timestr = hostupstr.group(2)
                self.bootupTimestamp = int(datetime.utcfromtimestamp(
                    parse(timestr).timestamp()).timestamp()*1000)
            else:
                self.logger.error(
                    f'Cannot parse uptime from {self.address}:{self.port}')
                self.bootupTimestamp = -1

            self._extract_nos_version(data)

    async def _ssh_gather(self, service_callback, cmd_list, cb_token, oformat,
                          timeout, only_one=False):
        """Run ssh for cmd in cmdlist and place output on service callback
           This is different from IOSXE to avoid reinit node info each time
        """

        result = []
        if cmd_list is None:
            await service_callback(result, cb_token)
            return

        if not self._conn or not self._stdin:
            await self._init_ssh()

        if not self._conn or not self._stdin:
            self.logger.error(f'Not connected to {self.address}:{self.port}')
            await service_callback({}, cb_token)
            return

        timeout = timeout or self.cmd_timeout
        async with self.cmd_pacer(self.per_cmd_auth):
            for cmd in cmd_list:
                try:
                    if self.slow_host:
                        await asyncio.sleep(IOS_SLEEP_BET_CMDS)
                    self._stdin.write(cmd + '\n')
                    output = await self.wait_for_prompt()
                    if 'Invalid input detected' in output:
                        status = -1
                    elif 'suzieq timeout' in output:
                        status = HTTPStatus.REQUEST_TIMEOUT
                    else:
                        status = 0
                    if isinstance(cb_token, RsltToken):
                        cb_token.node_token = self.bootupTimestamp
                    result.append(self._create_result(cmd, status, output))
                    continue
                except Exception as e:
                    self.current_exception = e
                    result.append(self._create_error(cmd))
                    if not isinstance(e, asyncio.TimeoutError):
                        self.logger.error(
                            f"Unable to connect to {self.hostname} for {cmd} "
                            f"due to {e}")
                        try:
                            await self._close_connection()
                            self.logger.debug("Closed conn successfully for "
                                              f"{self.hostname}")
                        except Exception as close_exc:
                            self.logger.error(
                                f"Caught an exception closing {self.hostname}"
                                f" for {cmd}: {close_exc}")
                    else:
                        self.logger.error(
                            f"Unable to connect to {self.hostname} {cmd} "
                            "due to timeout")
                    break

        await service_callback(result, cb_token)

    def _extract_nos_version(self, data: str) -> None:
        match = re.search(r', Version\s+([^ ,]+)', data)
        if match:
            self.version = match.group(1).strip()
        else:
            self.logger.warning(
                f'Cannot parse version from {self.address}:{self.port}')
            self.version = "all"


class IOSNode(IosXENode):
    '''Classic IOS Node-specific implementation'''

    async def _init_rest(self):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat='json', timeout=None):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')


class JunosNode(Node):
    '''Juniper's Junos node-specific implementation'''

    async def _init_rest(self):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat='json', timeout=None):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _fetch_init_dev_data(self):
        """Fill in the boot time of the node by running requisite cmd"""
        await self._exec_cmd(self._parse_init_dev_data,
                             ["show system uptime|display json",
                              "show version"], None, 'mixed')

    async def _parse_init_dev_data(self, output, cb_token) -> None:
        """Parse the uptime command output"""
        if output[0]["status"] == 0:
            data = output[0]["data"]
            try:
                jdata = json.loads(data.replace('\n', '').strip())
                if self.devtype not in ["junos-mx", "junos-qfx10k"]:
                    jdata = (jdata['multi-routing-engine-results'][0]
                             ['multi-routing-engine-item'][0])

                timestr = (jdata['system-uptime-information'][0]
                           ['system-booted-time'][0]['time-length'][0]
                           ['attributes'])
            except Exception:
                self.logger.warning(
                    f'Unable to parse junos boot time from {data}')
                timestr = '{"junos:seconds": "0"}'
            self.bootupTimestamp = (get_timestamp_from_junos_time(
                timestr, output[0]['timestamp']/1000)/1000)

        if (len(output) > 1) and (output[1]["status"] == 0):
            data = output[1]["data"]
            hmatch = re.search(r'\nHostname:\s+(\S+)\n', data)
            if hmatch:
                self._set_hostname(hmatch.group(1))

            self._extract_nos_version(data)

    def _extract_nos_version(self, data) -> None:
        """Extract the version from the output of show version"""
        match = re.search(r'Junos: (\S+)', data)
        if match:
            self.version = match.group(1).strip()
        else:
            self.logger.warning(
                f'Cannot parse version from {self.address}:{self.port}')
            self.version = "all"


class NxosNode(Node):
    '''Cisco's NXOS Node-specific implementation'''

    async def _init_rest(self):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat="json", timeout=None):
        '''Gather data for service via device REST API'''
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _fetch_init_dev_data(self):
        """Fill in the boot time of the node by running requisite cmd"""
        await self._exec_cmd(self._parse_init_dev_data,
                             ["show version", "show hostname"], None,
                             'mixed')

    async def _parse_init_dev_data(self, output, cb_token) -> None:
        """Parse the uptime command output"""

        hostname = ''

        if output[0]["status"] == 0:
            data = output[0]["data"]

            self._extract_nos_version(data)
            uptime_grp = re.search(r'Kernel\s+uptime\s+is\s+([^\n]+)', data)
            if uptime_grp:
                self.bootupTimestamp = parse(uptime_grp.group(1)).timestamp()

        if len(output) > 1:
            if output[1]["status"] == 0:
                hostname = output[1]["data"].strip()
        else:
            if output[0]['hostname'] != output[0]['address']:
                hostname = output[0]['hostname']

        if hostname:
            self._set_hostname(hostname)

    def _extract_nos_version(self, data: str) -> None:

        version = ''
        vgrp = re.search(r'system:\s+version\s+([^\n]+)', data)
        if vgrp:
            version = vgrp.group(1)
        else:
            vgrp = re.search(r'NXOS:\s+version\s+(\S+)', data)
            if vgrp:
                version = vgrp.group(1)
        if not version:
            self.logger.warning(
                f'Cannot parse version from {self.address}:{self.port}')
            self.version = "all"
        else:
            self.version = version


class SonicNode(Node):
    '''SONiC Node-specific implementtaion'''

    async def _init_rest(self):
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat="json", timeout=None):
        '''Gather data for service via device REST API'''
        raise NotImplementedError(
            f'{self.address}: REST transport is not supported')

    async def _fetch_init_dev_data(self):
        """Fill in the boot time of the node by running requisite cmd"""
        await self._exec_cmd(self._parse_init_dev_data,
                             ["cat /proc/uptime", "hostname", "show version"],
                             None, 'text')

    async def _parse_init_dev_data(self, output, cb_token) -> None:
        """Parse the uptime command output"""

        if output[0]["status"] == 0:
            upsecs = output[0]["data"].split()[0]
            self.bootupTimestamp = int(int(time.time()*1000)
                                       - float(upsecs)*1000)
        if (len(output) > 1) and (output[1]["status"] == 0):
            self.hostname = output[1]["data"].strip()
        if (len(output) > 2) and (output[2]["status"] == 0):
            self._extract_nos_version(output[1]["data"])

    def _extract_nos_version(self, data: str) -> None:
        match = re.search(r'Version:\s+SONiC-OS-([^-]+)', data)
        if match:
            self.version = match.group(1).strip()
        else:
            self.logger.warning(
                f'Cannot parse version from {self.address}:{self.port}')
            self.version = "all"


class PanosNode(Node):
    '''Node object representing access to a Palo Alto Networks FW'''

    async def _fetch_init_dev_data(self):
        discovery_cmd = 'show system info'
        try:
            res = []
            # temporary hack to detect device info using ssh
            async with self.cmd_pacer():
                async with asyncssh.connect(
                        self.address, port=22, username=self.username,
                        password=self.password, known_hosts=None) as conn:
                    async with conn.create_process() as process:
                        process.stdin.write(f'{discovery_cmd}\n')
                        output = ""
                        output += await process.stdout.read(1)
                        try:
                            await asyncio.wait_for(
                                process.wait_closed(), timeout=0.1)
                        except asyncio.TimeoutError:
                            pass

                        stdout, _ = process.collect_output()
                        output += stdout
                        res = [{
                            "status": 0,
                            "data": output}]

            await self._parse_init_dev_data(res, None)
            self._session = aiohttp.ClientSession(
                conn_timeout=self.connect_timeout,
                connector=aiohttp.TCPConnector(ssl=False),
            )
            if self.api_key is None:
                await self.get_api_key()
        except asyncssh.misc.PermissionDenied:
            self.logger.error(
                f'{self.address}:{self.port}: permission denied')
            self._retry -= 1
        except Exception as e:
            self.logger.error(
                f'{self.hostname}:{self.port}: Command "{discovery_cmd}" '
                f'failed due to {e}')

    async def get_api_key(self):
        """Authenticate to get the api key needed in all cmd requests"""
        url = f"https://{self.address}:{self.port}/api/?type=keygen&user=" \
            f"{self.username}&password={self.password}"

        if not self._retry:
            return
        async with self.cmd_pacer(self.per_cmd_auth):
            async with self._session.get(url, timeout=self.connect_timeout) \
                    as response:
                status, xml = response.status, await response.text()
                if status == 200:
                    data = xmltodict.parse(xml)
                    self.api_key = data["response"]["result"]["key"]
                    # reset retry count, just in case.
                    self._retry = self._max_retries_on_auth_fail
                elif status == 403:
                    self.logger.error('Invalid credentials, could not get api '
                                      f'key for {self.address}:{self.port}.')
                    self._retry -= 1
                else:
                    self.logger.error('Unknown error, could not get '
                                      'api key for '
                                      f'{self.address}:{self.port}.')

    async def _parse_init_dev_data(self, output, cb_token) -> None:
        """Parse the uptime command output"""
        if output[0]["status"] == 0:
            data = output[0]["data"]
            # extract uptime
            match = re.search(
                r'uptime:\s+(\d+)\sdays,\s(\d+):(\d+):(\d+)', data)

            if match:
                days = match.group(1).strip()
                hours = match.group(2).strip()
                minutes = match.group(3).strip()
                seconds = match.group(4).strip()
                upsecs = 86400 * int(days) + 3600 * int(hours) + \
                    60 * int(minutes) + int(seconds)
                self.bootupTimestamp = int(
                    int(time.time()*1000) - float(upsecs)*1000)
            else:
                self.logger.warning(
                    f'Cannot parse uptime from {self.address}:{self.port}')

            # extract hostname
            hmatch = re.search(r'hostname:\s+(\S+)\n', data)
            if hmatch:
                self.hostname = hmatch.group(1).strip()
            else:
                self.logger.warning(
                    f'Cannot parse hostname from {self.address}:{self.port}')

            self._extract_nos_version(data)

    def _extract_nos_version(self, data: str) -> None:
        vmatch = re.search(r'sw-version:\s+(\S+)', data)
        if vmatch:
            self.version = vmatch.group(1).strip()
        else:
            self.logger.warning(
                f'Cannot parse version from {self.address}:{self.port}')
            self.version = "all"

    async def _init_rest(self):
        # In case of PANOS, getting here means REST is up
        if not self._session:
            async with self.cmd_pacer(self.per_cmd_auth):
                try:
                    self._session = aiohttp.ClientSession(
                        conn_timeout=self.connect_timeout,
                        connector=aiohttp.TCPConnector(ssl=False),
                    )
                    if self.api_key is None:
                        await self.get_api_key()
                    # If the api_key is still None we can't gather any data.
                    # Ensure that the connection pool is closed and set it to
                    # None so that _rest_gather can fail gracefully.
                    if self.api_key is None:
                        self._session.close()
                        self._session = None
                except Exception as e:
                    self.logger.error(
                        f'{self.transport}://{self.hostname}:{self.port}, '
                        f'Unable to communicate due to error: {str(e)}')

    async def _rest_gather(self, service_callback, cmd_list, cb_token,
                           oformat="json", timeout=None):

        result = []
        if not cmd_list:
            return result

        timeout = timeout or self.connect_timeout

        now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

        url = f"https://{self.address}:{self.port}/api/"

        status = 200  # status OK

        # if there's no session we have failed to get init dev data
        if not self._session and self._retry:
            self._fetch_init_dev_data()

        # if there's still no session, we need to create an error
        if not self._session:
            for cmd in cmd_list:
                result.append(self._create_error(cmd))
            await service_callback(result, cb_token)
            return

        async with self.cmd_pacer(self.per_cmd_auth):
            try:
                for cmd in cmd_list:
                    url_cmd = f"{url}?type=op&cmd={cmd}&key={self.api_key}"
                    async with self._session.get(
                            url_cmd, timeout=timeout) as response:
                        status, xml = response.status, await response.text()
                        if status == 200:
                            json_out = json.dumps(
                                xmltodict.parse(xml))
                            result.append({
                                "status": status,
                                "timestamp": now,
                                "cmd": cmd,
                                "devtype": self.devtype,
                                "namespace": self.nsname,
                                "hostname": self.hostname,
                                "address": self.address,
                                "data": json_out,
                            })
                        else:
                            result.append(self._create_error(cmd))
                            self.logger.error(
                                f'{self.transport}://{self.hostname}:'
                                f'{self.port}: Command {cmd} failed with '
                                f'status {response.status}')
            except Exception as e:
                self.current_exception = e
                for cmd in cmd_list:
                    result.append(self._create_error(cmd))
                self.logger.error(
                    f"{self.transport}://{self.hostname}:{self.port} "
                    f"Unable to communicate due to {str(e)}")

        await service_callback(result, cb_token)
