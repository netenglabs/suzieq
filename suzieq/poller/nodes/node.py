import sys
from collections import defaultdict
import os
import time
from datetime import datetime, timezone
import logging
import random
from http import HTTPStatus
import json
import re

import yaml
from urllib.parse import urlparse

import asyncio
import asyncssh
import aiohttp
from dateparser import parse
from asyncio.subprocess import PIPE, DEVNULL
from concurrent.futures._base import TimeoutError

from suzieq.poller.services.service import RsltToken
from suzieq.poller.genhosts import convert_ansible_inventory
from suzieq.utils import get_timestamp_from_junos_time, known_devtypes

logger = logging.getLogger(__name__)


def get_hostsdata_from_hostsfile(hosts_file) -> dict:
    """Read the suzieq devices file and return the data from the file"""

    if not os.path.isfile(hosts_file):
        logger.error(f"Suzieq inventory {hosts_file} must be a file")
        print(f"ERROR: Suzieq inventory {hosts_file} must be a file")
        sys.exit(1)

    if not os.access(hosts_file, os.R_OK):
        logger.error("Suzieq inventory file is not readable: {}", hosts_file)
        print("ERROR: hosts Suzieq inventory file is not readable: {}",
              hosts_file)
        sys.exit(1)

    with open(hosts_file, "r") as f:
        try:
            data = f.read()
            hostsconf = yaml.safe_load(data)
        except Exception as e:
            logger.error("Invalid Suzieq inventory file:{}", e)
            print("Invalid Suzieq inventory file:{}", e)
            sys.exit(1)

    if not hostsconf or isinstance(hostsconf, str):
        logger.error(f"Invalid Suzieq inventory file:{hosts_file}")
        print(f"ERROR: Invalid hosts Suzieq inventory file:{hosts_file}")
        sys.exit(1)

    if not isinstance(hostsconf, list):
        if '_meta' in hostsconf.keys():
            logger.error("Invalid Suzieq inventory format, Ansible format??"
                         " Use -a instead of -D with inventory")
            print("ERROR: Invalid Suzieq inventory format, Ansible format??"
                  " Use -a instead of -D with inventory")
        else:
            logger.error(f"Invalid Suzieq inventory file:{hosts_file}")
            print(f"ERROR: Invalid hosts Suzieq inventory file:{hosts_file}")
        sys.exit(1)

    for conf in hostsconf:
        if any(x not in conf.keys() for x in ['namespace', 'hosts']):
            logger.error("Invalid inventory:{}, no namespace/hosts sections")
            print("ERROR: Invalid inventory:{}, no namespace/hosts sections")
            sys.exit(1)

    return hostsconf


async def init_hosts(**kwargs):
    """Process list of devices to gather data from.
    This involves creating a node for each device listed, and connecting to
    those devices and initializing state about those devices
    """

    nodes = {}

    inventory = kwargs.pop('inventory', None)
    if not inventory:
        ans_inventory = kwargs.pop('ans_inventory', None)
    else:
        _ = kwargs.pop('ans_inventory', None)
        ans_inventory = None

    namespace = kwargs.pop('namespace', 'default')
    passphrase = kwargs.pop('passphrase', None)
    ssh_config_file = kwargs.pop('ssh_config_file', None)
    jump_host = kwargs.pop('jump_host', None)
    jump_host_key_file = kwargs.pop('jump_host_key_file', None)
    ignore_known_hosts = kwargs.pop('ignore_known_hosts', False)
    user_password = kwargs.pop('password', None)

    if kwargs:
        logger.error(f'Received unrecognized keywords {kwargs}, aborting')
        sys.exit(1)

    if inventory:
        hostsconf = get_hostsdata_from_hostsfile(inventory)
    else:
        hostsconf = yaml.safe_load('\n'.join(
            convert_ansible_inventory(ans_inventory, namespace)))

    if not hostsconf:
        logger.error("No hosts specified in inventory file")
        print("ERROR: No hosts specified in inventory file")
        sys.exit(1)

    if jump_host_key_file:
        if not jump_host:
            logger.error("Jump host key file specified without jump host")
            print("ERROR: Jump host key file specified without jump host")
            sys.exit(1)
        else:
            if not os.access(jump_host_key_file, os.F_OK):
                logger.error(
                    f"Jump host key file {jump_host_key_file} does not exist")
                print(f"ERROR: Jump host key file {jump_host_key_file} "
                      f"does not exist")
                sys.exit(1)
            if not os.access(jump_host_key_file, os.R_OK):
                logger.error(
                    f"Jump host key file {jump_host_key_file} not readable")
                print(f"ERROR: Jump host key file {jump_host_key_file} "
                      f"not readable")
                sys.exit(1)

    for namespace in hostsconf:
        nsname = namespace["namespace"]

        tasks = []
        hostlist = namespace.get("hosts", [])
        if not hostlist:
            logger.error(f'No hosts in namespace {nsname}')
            continue

        for host in hostlist:
            if not isinstance(host, dict):
                logger.error(f'Ignoring invalid host specification: {host}')
                continue
            entry = host.get("url", None)
            if entry:
                words = entry.split()
                result = urlparse(words[0])

                username = result.username
                password = result.password or user_password or "vagrant"
                port = result.port
                host = result.hostname
                devtype = None
                keyfile = None

                try:
                    for i in range(1, len(words[1:])+1):
                        if words[i].startswith('keyfile'):
                            keyfile = words[i].split("=")[1]
                        elif words[i].startswith('devtype'):
                            devtype = words[i].split("=")[1]
                        elif words[i].startswith('username'):
                            username = words[i].split("=")[1]
                        elif words[i].startswith('password'):
                            password = words[i].split("=")[1]
                except IndexError:
                    logger.error(f'Invalid key/value {words}, missing "="')
                    logger.error(f'Ignoring node {host}')
                    continue

                newnode = Node()
                tasks += [newnode._init(
                    address=host,
                    username=username,
                    port=port,
                    password=password,
                    passphrase=passphrase,
                    transport=result.scheme,
                    devtype=devtype,
                    ssh_keyfile=keyfile,
                    ssh_config_file=ssh_config_file,
                    jump_host=jump_host,
                    jump_host_key_file=jump_host_key_file,
                    namespace=nsname,
                    ignore_known_hosts=ignore_known_hosts,
                )]
            else:
                logger.error(f'Ignoring invalid host specification: {entry}')

        if not tasks:
            logger.error("No hosts detected in provided inventory file")
            return []

        for f in asyncio.as_completed(tasks):
            newnode = await f
            if newnode.devtype is None:
                logger.error(
                    "Unable to determine device type for {}:{}"
                    .format(newnode.address, newnode.port))
            else:
                logger.info(f"Added node {newnode.hostname}:{newnode.port}")

            nodes.update(
                {"{}.{}".format(nsname, newnode.hostname): newnode})

    return nodes


class Node(object):
    @property
    def status(self):
        return self._status

    @property
    def last_exception(self) -> Exception:
        return self._last_exception

    @last_exception.setter
    def last_exception(self, val: Exception):
        self._last_exception = val
        self._last_exception_timestamp = int(time.time()*1000)

    async def _init(self, **kwargs):
        if not kwargs:
            raise ValueError

        self.hostname = "-"  # Device hostname
        self.devtype = None  # Device type
        self.pvtkey_file = ""     # SSH private keyfile
        self.prev_result = {}  # No updates if nothing changed
        self.nsname = None
        self.svc_cmd_mapping = defaultdict(lambda: {})  # Not used yet
        self.logger = logging.getLogger(__name__)
        self.port = 0
        self.backoff = 15  # secs to backoff
        self.init_again_at = 0  # after this epoch secs, try init again
        self.connect_timeout = 10  # connect timeout in seconds
        self.cmd_timeout = 10  # default command timeout in seconds
        self.batch_size = 4    # Number of commands to issue in parallel
        self.bootupTimestamp = 0
        self.version = 0                 # OS Version to pick the right defn
        self._service_queue = None
        self._conn = None
        self._tunnel = None
        self._status = "init"
        self.svcs_proc = set()
        self.error_svcs_proc = set()
        self.ssh_ready = asyncio.Event()
        self._last_exception = None
        self._last_exception_timestamp = None
        self.sigend = False

        self.address = kwargs["address"]
        self.hostname = kwargs["address"]  # default till we get hostname
        self.username = kwargs.get("username", "vagrant")
        self.password = kwargs.get("password", "vagrant")
        self.transport = kwargs.get("transport", "ssh")
        self.nsname = kwargs.get("namespace", "default")
        self.port = kwargs.get("port", 0)
        self.devtype = None
        self.ssh_config_file = kwargs.get("ssh_config_file", None)

        passphrase = kwargs.get("passphrase", None)
        jump_host = kwargs.get("jump_host", "")
        if jump_host:
            jump_result = urlparse(jump_host)
            self.jump_user = jump_result.username or self.username
            self.jump_host = jump_result.hostname
            if jump_result.port:
                self.jump_port = jump_result.port
            else:
                self.jump_port = 22
            pvtkey_file = kwargs.pop('jump_host_key_file')
            if pvtkey_file:
                self.jump_host_key_file = self._decrypt_pvtkey(pvtkey_file,
                                                               passphrase)
                if not self.jump_host_key_file:
                    self.logger.error("ERROR: terminating poller")
                    self.jump_host_key_file = None
                    sys.exit(1)
        else:
            self.jump_host = None
            self.jump_host_key_file = None

        self.ignore_known_hosts = kwargs.get('ignore_known_hosts', False)
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

        self.ssh_ready.set()
        if not self.port:
            if self.transport == "ssh":
                self.port = 22
            elif self.transport == "https":
                self.port = 443

        if self.transport == "ssh":
            await self._init_ssh(init_boot_time=False)

        devtype = kwargs.get("devtype", None)
        if devtype:
            self.set_devtype(devtype)

        await self.init_node()
        if not self.hostname:
            self.hostname = self.address

        if self._status == "init":
            self.backoff = min(600, self.backoff * 2) + \
                (random.randint(0, 1000) / 1000)
            self.init_again_at = time.time() + self.backoff
        return self

    def _decrypt_pvtkey(self, pvtkey_file: str, passphrase: str) -> str:
        """Decrypt private key file"""

        keydata: str = None
        if pvtkey_file:
            try:
                keydata = asyncssh.public_key.read_private_key(pvtkey_file,
                                                               passphrase)
            except Exception as e:
                self.logger.error(
                    f"ERROR: Unable to read private key file {pvtkey_file}"
                    f"for jump host due to {str(e)}")

        return keydata

    async def init_node(self):
        devtype = None
        hostname = None

        if self.transport == "ssh" or self.transport == "local":
            try:
                await self.get_device_type_hostname()
                devtype = self.devtype
            except Exception as e:
                self.last_exception = e
                devtype = None

            if not devtype:
                self.logger.debug(
                    f"no devtype for {self.hostname} {self.last_exception}")
                self._status = "init"
                return
            else:
                self.set_devtype(devtype)
                self._status = "good"

                self.set_hostname(hostname)

            await self.init_boot_time()

    def set_devtype(self, devtype):
        """Change the class based on the device type"""

        self.devtype = devtype
        if not devtype:
            return
        if devtype not in known_devtypes():
            self.logger.error(f'An unknown devtype {devtype} is being added.'
                              f' This will cause problems. '
                              f'Node {self.address}:{self.port}')
            raise ValueError

        if self.devtype == "cumulus":
            self.__class__ = CumulusNode
        elif self.devtype == "eos":
            self.__class__ = EosNode
        elif self.devtype == "iosxr":
            self.__class__ = IosXRNode
        elif self.devtype.startswith("junos"):
            self.__class__ = JunosNode
        elif self.devtype == "nxos":
            self.__class__ = NxosNode
        elif self.devtype.startswith("sonic"):
            self.__class__ == SonicNode

    async def get_device_type_hostname(self):
        """Determine the type of device we are talking to if using ssh/local"""
        # There isn't that much of a difference in running two commands versus
        # running them one after the other as this involves an additional ssh
        # setup time. show version works on most networking boxes and
        # hostnamectl on Linux systems. That's all we support today.
        await self.exec_cmd(self._parse_device_type_hostname,
                            ["show version", "hostnamectl",
                             "cat /etc/os-release", "show hostname"], None,
                            'text')

    async def _parse_device_type_hostname(self, output, cb_token) -> None:
        devtype = ""
        hostname = None

        if output[0]["status"] == 0:
            data = output[0]["data"]
            if "Arista " in data:
                devtype = "eos"
            elif "JUNOS " in data:
                model = re.search(r'Model:\s+(\S+)', data)
                if model:
                    if 'mx' in model.group(1):
                        devtype = 'junos-mx'
                    elif 'qfx' in model.group(1):
                        devtype = 'junos-qfx'
                    elif 'ex' in model.group(1):
                        devtype = 'junos-ex'
                    elif 'srx' in model.group(1):
                        devtype = 'junos-es'
                if not devtype:
                    devtype = "junos"
            elif "NX-OS" in data:
                devtype = "nxos"
            elif "SONiC" in data:
                devtype = "sonic"
            elif "Cisco IOS XR" in data:
                devtype = "iosxr"
            elif any(x in data for x in ['vEOS', 'Arista']):
                devtype = "eos"

            if devtype.startswith("junos"):
                hmatch = re.search(r'Hostname:\s+(\S+)\n', data)
                if hmatch:
                    hostname = hmatch.group(1)
            elif devtype == "nxos":
                data = output[3]["data"]
                hostname = data.strip()
            elif devtype == "eos":
                data = output[3]['data']
                lines = data.split('\n')
                hostname = lines[1].split('FQDN:')[1].strip()
            elif devtype != "iosxr" and output[3]["status"] == 0:
                hostname = output[3]["data"].strip()

        elif output[1]["status"] == 0:
            data = output[1]["data"]
            if "Cumulus Linux" in data:
                devtype = "cumulus"
            else:
                devtype = "linux"

            # Hostname is in the first line of hostnamectl
            hostline = data.splitlines()[0].strip()
            if hostline.startswith("Static hostname"):
                _, hostname = hostline.split(":")
                hostname = hostname.strip()

            if output[2]["status"] == 0:
                data = output[2]["data"]
                for line in data.splitlines():
                    if line.startswith("VERSION_ID"):
                        self.version = line.split('=')[1] \
                                           .strip().replace('"', '')
                        break

        if not devtype and not self.last_exception:
            self.logger.warning(
                f'Unable to determine devtype for {self.address}:{self.port}')
            self._status = 'init'
            self.last_exception = 'No devtype'
        else:
            self.logger.info(
                f'Detected {devtype} for {self.address}:{self.port}, {hostname}')
            self.set_devtype(devtype)
            self.set_hostname(hostname)
            self.last_exception = ''

    async def _parse_boottime_hostname(self, output, cb_token) -> None:
        """Parse the uptime command output"""

        if self.sigend:
            return

        if output[0]["status"] == 0:
            upsecs = output[0]["data"].split()[0]
            self.bootupTimestamp = int(int(time.time()*1000)
                                       - float(upsecs)*1000)
        if output[1]["status"] == 0:
            self.hostname = output[1]["data"].strip()

    def set_unreach_status(self):
        self._status = "unreachable"

    def set_good_status(self):
        self._status = "good"

    def is_alive(self):
        return self._status == "good"

    def set_hostname(self, hostname=None):
        if hostname:
            self.hostname = hostname

    async def local_gather(self, service_callback, cmd_list, oformat,
                           cb_token) -> None:
        """Given a dictionary of commands, run locally and return outputs"""

        result = []
        for cmd in cmd_list:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=PIPE,
                                                         stderr=PIPE)

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.cmd_timeout)

                if not proc.returncode:
                    d = stdout.decode('ascii', 'ignore')
                    result.append(self._create_result(cmd))
                else:
                    d = stderr('ascii', 'ignore')
                    result.append(self._create_error(cmd))

            except asyncio.TimeoutError as e:
                if self.sigend:
                    self._terminate()
                    return

                self.last_exception = e
                result.append(self._create_error(cmd))

        await service_callback(result, cb_token)

    async def init_boot_time(self):
        """Fill in the boot time of the node by running the appropriate command"""
        await self.exec_cmd(self._parse_boottime_hostname,
                            ["cat /proc/uptime", "hostname"], None, 'text')

    def post_commands(self, service_callback, svc_defn: dict,
                      cb_token: RsltToken):
        if cb_token:
            cb_token.nodeQsize = self._service_queue.qsize()
        self._service_queue.put_nowait([service_callback, svc_defn, cb_token])

    async def run(self):
        tasks = []
        while True:
            if self.sigend:
                self._terminate()
                return

            while (len(tasks) < self.batch_size):
                try:
                    request = await self._service_queue.get()
                except asyncio.CancelledError:
                    await self._terminate()
                    return

                if request:
                    tasks.append(self.exec_service(
                        request[0], request[1], request[2]))
                    self.logger.debug(
                        f"Scheduling {request[2].service} for execution")
                if self._service_queue.empty():
                    break

            if tasks:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED)

                tasks = list(pending)

    async def ssh_gather(self, service_callback, cmd_list, cb_token, oformat,
                         timeout):
        """Run ssh for cmd in cmdlist and place output on service callback"""

        result = []

        if cmd_list is None:
            await service_callback({}, cb_token)

        if not self._conn:
            await self._init_ssh()
            if not self._conn:
                for cmd in cmd_list:
                    self.logger.error(
                        "Unable to connect to node {} cmd {}".format(
                            self.hostname, cmd))
                    result.append(self._create_error(cmd))
                await service_callback(result, cb_token)
                return

        if isinstance(cb_token, RsltToken):
            cb_token.node_token = self.bootupTimestamp

        timeout = timeout or self.cmd_timeout
        for cmd in cmd_list:
            try:
                output = await asyncio.wait_for(self._conn.run(cmd),
                                                timeout=timeout)
                result.append(self._create_result(
                    cmd, output.exit_status, output.stdout))
            except Exception as e:
                if self.sigend:
                    self._terminate()
                    return
                self.last_exception = e
                result.append(self._create_error(cmd))
                if not isinstance(e, asyncio.TimeoutError):
                    self.logger.error(
                        f"Unable to connect to {self.hostname} for {cmd} "
                        f"due to {str(e)}")
                    await self._close_connection()
                else:
                    self.logger.error(
                        f"Unable to connect to {self.hostname} {cmd} "
                        "due to timeout")

                break

        await service_callback(result, cb_token)

    async def _close_connection(self):
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
        if self._tunnel:
            self._tunnel.close()
            await self._tunnel.wait_closed()

        self._conn = None
        self._tunnel = None

    async def _terminate(self):
        self.logger.warning(
            f'Node: {self.hostname} received signal to terminate')
        await self._close_connection()
        return

    def _init_service_queue(self):
        if not self._service_queue:
            self._service_queue = asyncio.Queue()

    async def _init_ssh(self, init_boot_time=True, rel_lock=True) -> None:
        await self.ssh_ready.wait()
        if not self._conn:
            self.ssh_ready.clear()
            if self.ignore_known_hosts:
                options = asyncssh.SSHClientConnectionOptions(
                    client_keys=self.pvtkey if self.pvtkey else None,
                    login_timeout=self.cmd_timeout,
                    password=self.password if not self.pvtkey else None,
                    known_hosts=None,
                    config=self.ssh_config_file
                )
            else:
                options = asyncssh.SSHClientConnectionOptions(
                    client_keys=self.pvtkey if self.pvtkey else None,
                    login_timeout=self.cmd_timeout,
                    password=self.password if not self.pvtkey else None,
                    config=self.ssh_config_file,
                )

            if self.jump_host_key_file:
                if self.ignore_known_hosts:
                    jump_host_options = asyncssh.SSHClientConnectionOptions(
                        client_keys=self.jump_host_key_file,
                        login_timeout=self.cmd_timeout,
                        known_hosts=None,
                        config=self.ssh_config_file,
                    )
                else:
                    jump_host_options = asyncssh.SSHClientConnectionOptions(
                        client_keys=self.jump_host_key_file,
                        login_timeout=self.cmd_timeout,
                        config=self.ssh_config_file,
                    )
            else:
                jump_host_options = options

            try:
                if self.jump_host:
                    self.logger.info(
                        'Using jump host: {}, with username: {}, and port: {}'
                        .format(self.jump_host, self.jump_user, self.jump_port)
                    )
                    self._tunnel = await asyncssh.connect(
                        self.jump_host, port=self.jump_port,
                        options=jump_host_options, username=self.jump_user)
                    self.logger.info(
                        f'Connection to jump host {self.jump_host} succeeded')

            except Exception as e:
                if self.sigend:
                    self._terminate()
                    return
                self.logger.error(
                    f"ERROR: Cannot connect to jump host: {self.jump_host}, "
                    f" {str(e)}")
                self.last_exception = e
                self._conn = None
                self._tunnel = None
                if rel_lock:
                    self.ssh_ready.set()
                return

            try:
                self._conn = await asyncssh.connect(
                    self.address,
                    username=self.username,
                    port=self.port,
                    options=options)

                self.logger.info(
                    f"Connected to {self.address}:{self.port} at {time.time()}")
                if init_boot_time:
                    await self.init_boot_time()
                elif rel_lock:
                    self.ssh_ready.set()
            except Exception as e:
                if self.sigend:
                    self._terminate()
                    return
                self.logger.error("ERROR: Unable to connect to "
                                  f"{self.address}:{self.port}, {str(e)}")
                self.last_exception = e
                self._conn = None
                self._tunnel = None
                if rel_lock:
                    self.ssh_ready.set()
        return

    def _create_error(self, cmd) -> dict:
        data = {'error': str(self.last_exception)}
        if isinstance(self.last_exception, TimeoutError):
            status = HTTPStatus.REQUEST_TIMEOUT
        elif isinstance(self.last_exception, asyncssh.misc.ProtocolError):
            status = HTTPStatus.FORBIDDEN
        elif hasattr(self.last_exception, 'code'):
            status = self.last_exception.code
        else:
            status = -1
        return self._create_result(cmd, status, data)

    def _create_result(self, cmd, status, data) -> dict:
        result = {
            "status": status,
            "timestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
            "cmd": cmd,
            "devtype": self.devtype,
            "namespace": self.nsname,
            "hostname": self.hostname,
            "address": self.address,
            "version": self.version,
            "data": data,
        }
        return result

    async def rest_gather(self, svc_dict, oformat="json"):
        raise NotImplementedError

    async def exec_cmd(self, service_callback, cmd_list, cb_token,
                       oformat='json', timeout=None):

        if self.transport == "ssh":
            await self.ssh_gather(service_callback, cmd_list, cb_token, oformat,
                                  timeout)
        elif self.transport == "https":
            await self.rest_gather(service_callback, cmd_list,
                                   cb_token, oformat, timeout)
        elif self.transport == "local":
            await self.local_gather(service_callback, cmd_list,
                                    cb_token, oformat, timeout)
        else:
            self.logger.error(
                "Unsupported transport {} for node {}".format(
                    self.transport, self.hostname
                )
            )

        return

    async def exec_service(self, service_callback, svc_defn: dict,
                           cb_token: RsltToken):

        result = []  # same type as gather function
        cmd = None
        if not svc_defn:
            return result

        if self._status == "init":
            if self.init_again_at < time.time():
                await self.init_node()

        if self._status == "init":
            result.append(self._create_error(svc_defn.get("service", "-")))
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

        # TODO This kind of logic should be encoded in config and node shouldn't have to know about it
        if "copy" in use:
            use = svc_defn.get(use.get("copy"))

        if use:
            if isinstance(use, list):
                # There's more than one version here, we have to pick ours
                for item in use:
                    if (item["version"] == "all" or
                            item["version"] == self.version):
                        cmd = item.get("command", None)
                        break
            else:
                cmd = use.get("command", None)

        if not cmd:
            return result

        oformat = use.get('format', 'json')
        if type(cmd) is not list:
            if use.get('textfsm'):
                oformat = 'text'
            cmdlist = [cmd]
        else:
            # TODO: Handling format for the multiple cmd case
            cmdlist = [x.get('command', '') for x in cmd]

        await self.exec_cmd(service_callback, cmdlist, cb_token,
                            oformat=oformat, timeout=cb_token.timeout)


class EosNode(Node):
    def _init(self, **kwargs):
        super()._init(**kwargs)
        self.devtype = "eos"

    async def init_node(self):
        try:
            await self.get_device_boottime_hostname()
        except Exception as e:
            if self.sigend:
                self._terminate()
                return
            self.last_exception = e

    async def get_device_boottime_hostname(self):
        """Determine the type of device we are talking to"""

        if self.transport == 'https':
            cmdlist = ["show version", "show hostname"]
        else:
            cmdlist = ["show version|json", "show hostname|json"]
        await self.exec_cmd(self._parse_boottime_hostname, cmdlist, None)

    async def _parse_boottime_hostname(self, output, cb_token) -> None:

        if output[0]["status"] == 0 or output[0]["status"] == 200:
            if self.transport == 'ssh':
                try:
                    data = json.loads(output[0]["data"])
                except json.JSONDecodeError:
                    self.logger.error(
                        f'nodeinit: Error decoding JSON for {self.address}:{self.port}')
                    self._status = 'init'
                    return
            else:
                data = output[0]["data"]
            self.bootupTimestamp = data["bootupTimestamp"]

        if output[1]["status"] == 0 or output[1]["status"] == 200:
            if self.transport == 'ssh':
                try:
                    data = json.loads(output[1]["data"])
                except json.JSONDecodeError:
                    self.logger.error(
                        f'nodeinit: Error decoding JSON for {self.address}:{self.port}')
                    self._status = 'init'
                    return
            else:
                data = output[1]["data"]
            self.hostname = data["fqdn"]
            self._status = "good"

    async def ssh_gather(self, service_callback, cmd_list, cb_token, oformat,
                         timeout):
        """Run ssh and place output on service callback for dict of cmds"""

        # We need to add the JSON option for all commands that support JSON
        # output since the command provided assumes REST API
        newcmd_list = []
        for cmd in cmd_list:
            if (oformat == "json") and not cmd.endswith('json'):
                cmd += '| json'

            newcmd_list.append(cmd)

        return await super().ssh_gather(service_callback, newcmd_list,
                                        cb_token, oformat, timeout)

    async def rest_gather(self, service_callback, cmd_list, cb_token,
                          oformat="json", timeout=None):

        result = []
        if not cmd_list:
            return result

        timeout = timeout or self.cmd_timeout

        now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        auth = aiohttp.BasicAuth(self.username, password=self.password)
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

        try:
            async with aiohttp.ClientSession(
                    auth=auth,
                    conn_timeout=self.connect_timeout,
                    read_timeout=timeout,
                    connector=aiohttp.TCPConnector(ssl=False),
            ) as session:
                async with session.post(url, json=data, headers=headers) as response:
                    status, json_out = response.status, await response.json()
                    if "result" in json_out:
                        output.extend(json_out["result"])
                    else:
                        output.extend(json_out["error"])

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
                        "data": output[i] if type(output) is list else output,
                    }
                )
        except Exception as e:
            if self.sigend:
                self._terminate()
                return
            self.last_exception = e
            for cmd in cmd_list:
                result.append(self._create_error(cmd))
            self._status = "init"  # Recheck everything
            self.logger.error("ERROR: (REST) Unable to communicate with node "
                              "{}:{} due to {}".format(
                                  self.address, self.port, str(e)))

        await service_callback(result, cb_token)

    async def _parse_hostname(self, output, cb_token) -> None:
        """Parse the hostname command output"""
        if not output:
            self.hostname = "-"
            return

        if output[0]["status"] == 0:
            data = output[1]["data"]
            try:
                jout = json.loads(data)
                self.hostname = jout["hostname"]
            except:
                self.hostname = "-"


class CumulusNode(Node):
    def _init(self, **kwargs):
        if "username" not in kwargs:
            kwargs["username"] = "cumulus"
        if "password" not in kwargs:
            kwargs["password"] = "CumulusLinux!"

        super()._init(**kwargs)
        self.devtype = "cumulus"

    async def rest_gather(self, service_callback, cmd_list, cb_token,
                          oformat='json', timeout=None):

        result = []
        if not cmd_list:
            return result

        auth = aiohttp.BasicAuth(self.username, password=self.password)
        url = "https://{0}:{1}/nclu/v1/rpc".format(self.address, self.port)
        headers = {"Content-Type": "application/json"}

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
                        result.append(
                            {
                                "status": response.status,
                                "timestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
                                "cmd": cmd,
                                "devtype": self.devtype,
                                "namespace": self.nsname,
                                "hostname": self.hostname,
                                "address": self.address,
                                "data": await response.text(),
                            }
                        )
        except Exception as e:
            if self.sigend:
                self._terminate()
                return
            self.last_exception = e
            result.append(self._create_error(cmd))
            self.logger.error("ERROR: (REST) Unable to communicate with node "
                              "{}:{} due to {}".format(
                                  self.address, self.port, str(e)))

        await service_callback(result, cb_token)


class IosXRNode(Node):

    async def _init_ssh(self, init_boot_time=True) -> None:
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
        while True:
            await super()._init_ssh(init_boot_time=False, rel_lock=False)
            if self._conn:
                break
            else:
                await asyncio.sleep(backoff_period)
                backoff_period *= 2
                if backoff_period > 120:
                    backoff_period = 120
                self.ssh_ready.set()
        if self._conn:
            try:
                self._long_proc = await self._conn.create_process(
                    'run tail -s 3600 -f /etc/version', stdout=DEVNULL,
                    stderr=DEVNULL)
                self.logger.info(
                    f'Persistent SSH present for {self.hostname}')
            except Exception:
                self._conn = None
                return

        if not self.hostname:
            await self.init_boot_time()
        self.ssh_ready.set()

    async def init_boot_time(self):
        """Fill in the boot time of the node by running requisite cmd"""
        await self.exec_cmd(self._parse_boottime_hostname,
                            ["show version", "show run hostname"], None)

    async def _parse_boottime_hostname(self, output, cb_token) -> None:
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

        if output[1]["status"] == 0:
            data = output[1]['data']
            hostname = re.search(r'hostname (\S+)', data.strip())
            if hostname:
                self.hostname = hostname.group(1)
                self.logger.error(f'set hostname of {self.address}:{self.port} to '
                                  f'{hostname.group(1)}')
        self.ssh_ready.set()


class JunosNode(Node):

    async def init_boot_time(self):
        """Fill in the boot time of the node by running requisite cmd"""
        await self.exec_cmd(self._parse_boottime_hostname,
                            ["show system uptime|display json",
                             "show version"], None, 'mixed')

    async def _parse_boottime_hostname(self, output, cb_token) -> None:
        """Parse the uptime command output"""
        if output[0]["status"] == 0:
            data = output[0]["data"]
            try:
                jdata = json.loads(data.replace('\n', '').strip())
                if self.devtype != "junos-mx":
                    jdata = jdata['multi-routing-engine-results'][0]['multi-routing-engine-item'][0]

                timestr = jdata['system-uptime-information'][0]['system-booted-time'][0]['time-length'][0]['attributes']
            except Exception:
                self.logger.warning(
                    f'Unable to parse junos boot time from {data}')
                timestr = '{"junos:seconds": "0"}'
            self.bootupTimestamp = (get_timestamp_from_junos_time(
                timestr, output[0]['timestamp']/1000)/1000)

        if output[1]["status"] == 0:
            data = output[0]["data"]
            hmatch = re.search(r'\nHostname:\s+(\S+)\n', data)
            if hmatch:
                self.set_hostname(hmatch.group(1))


class NxosNode(Node):

    async def init_boot_time(self):
        """Fill in the boot time of the node by running requisite cmd"""
        await self.exec_cmd(self._parse_boottime_hostname,
                            ["show version|json", "show hostname"], None,
                            'mixed')

    async def _parse_boottime_hostname(self, output, cb_token) -> None:
        """Parse the uptime command output"""

        hostname = ''
        if output[0]["status"] == 0:
            data = json.loads(output[0]["data"])
            upsecs = (24*3600*int(data.get('kern_uptm_days', 0)) +
                      3600*int(data.get('kern_uptm_hrs', 0)) +
                      60*int(data.get('kern_uptm_mins', 0)) +
                      int(data.get('kern_uptm_secs', 0)))
            if upsecs:
                self.bootupTimestamp = int(int(time.time()*1000)
                                           - float(upsecs)*1000)
        if len(output) > 1:
            if output[1]["status"] == 0:
                hostname = output[1]["data"].strip()
        else:
            if output[0]['hostname'] != output[0]['address']:
                hostname = output[0]['hostname']

        if hostname:
            self.set_hostname(hostname)


class SonicNode(Node):

    async def init_boot_time(self):
        """Fill in the boot time of the node by running requisite cmd"""
        await self.exec_cmd(self._parse_boottime_hostname,
                            ["cat /proc/uptime", "hostname"], None, 'text')

    async def _parse_boottime_hostname(self, output, cb_token) -> None:
        """Parse the uptime command output"""

        if output[0]["status"] == 0:
            upsecs = output[0]["data"].split()[0]
            self.bootupTimestamp = int(int(time.time()*1000)
                                       - float(upsecs)*1000)
        if output[1]["status"] == 0:
            self.hostname = output[1]["data"].strip()
