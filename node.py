

from collections import defaultdict
import os
import time
from ipaddress import ip_address
import logging
import random

import json
import yaml
from urllib.parse import urlparse

import asyncio
import asyncio.futures as futures
import asyncssh
import aiohttp
from asyncio.subprocess import PIPE


async def init_hosts(hosts_file):
    '''Process list oof hosts
    This involves creating a node for each host listed, firing up services
    for which we need to pull data.'''

    nodes = {}

    if not os.path.isfile(hosts_file):
        logging.error('hosts config must be a file: {}', hosts_file)
        return nodes

    if not os.access(hosts_file, os.R_OK):
        logging.error('hosts config file is not readable: {}', hosts_file)
        return nodes

    with open(hosts_file, 'r') as f:
        try:
            hostsconf = yaml.safe_load(f.read())
        except Exception as e:
            logging.error('Invalid hosts config file:{}', e)
            print('Invalid hosts config file:{}', e)
            sys.exit(1)

    for datacenter in hostsconf:
        if 'datacenter' not in datacenter:
            logging.warning('No datacenter specified, assuming "default"')
            dcname = "default"
        else:
            dcname = datacenter['datacenter']

        for host in datacenter.get('hosts', None):
            entry = host.get('url', None)
            if entry:
                words = entry.split()
                result = urlparse(words[0])

                username = result.username
                password = result.password or 'vagrant'
                port = result.port
                host = result.hostname
                devtype = None

                if len(words) > 1 and '=' in words[1]:
                    devtype = words[1].split('=')[1]

                newnode = Node()
                await newnode._init(address=host, username=username,
                                    port=port, password=password,
                                    transport=result.scheme,
                                    devtype=devtype, datacenter=dcname)

                if newnode.devtype is None:
                    logging.error('Unable to determine device type for {}'
                                  .format(host))
                else:
                    logging.info('Added node {}'.format(newnode.hostname))

                nodes.update({'{}.{}'.format(dcname, newnode.hostname): newnode})

    return nodes


class Node(object):
    address = None              # Device IP or hostname if DNS'able
    hostname = ''               # Device hostname
    devtype = None              # Device type
    username = ''
    password = ''
    pvtkey = ''                 # Needed for Junos Vagrant
    transport = 'ssh'
    prev_result = {}            # No updates if nothing changed
    dcname = None
    status = 'good'
    svc_cmd_mapping = defaultdict(lambda: {})
    port = 0
    backoff = 15                # secs to backoff
    init_again_at = 0           # after this epoch secs, try init again

    async def _init(self, **kwargs):
        if not kwargs:
            raise ValueError

        self.address = kwargs['address']
        self.username = kwargs.get('username', 'vagrant')
        self.password = kwargs.get('password', 'vagrant')
        self.transport = kwargs.get('transport', 'ssh')
        self.dcname = kwargs.get('datacenter', "default")
        self.port = kwargs.get('port', 0)
        self.devtype = kwargs.get('devtype', None)
        pvtkey_file = kwargs.get('pvtkey_file', None)
        if pvtkey_file:
            self.pvtkey = asyncssh.public_key.read_private_key(pvtkey_file)

        if not self.port:
            if self.transport == 'ssh':
                self.port = 22
            elif self.transport == 'https':
                self.port = 443

        await self.init_node()
        if not self.hostname:
            self.hostname = self.address

        if self.status == 'init':
            self.backoff = (min(600, self.backoff * 2) +
                            (random.randint(0, 1000) / 1000))
            self.init_again_at = time.time() + self.backoff

        return self

    async def init_node(self):
        devtype = None
        hostname = None

        if self.transport == 'ssh' or self.transport == 'local':
            try:
                await self.get_device_type_hostname()
                devtype = self.devtype
            except (OSError, futures.TimeoutError) as e:
                devtype = None

            if devtype is None:
                self.status = 'init'
                return
            else:
                self.status = 'good'
                self.set_devtype(devtype)
                if hostname:
                    self.hostname = hostname
        elif self.devtype:
            self.set_devtype(self.devtype)
            if not self.hostname:
                await self.set_hostname()

    def set_devtype(self, devtype):
        self.devtype = devtype

        if self.devtype == 'cumulus':
            self.__class__ = CumulusNode
        elif self.devtype == 'eos':
            self.__class__ = EosNode
        elif any(n == self.devtype for n in ['Ubuntu', 'Debian',
                                             'Red Hat', 'Linux']):
            self.__class__ = LinuxNode
            self.devtype = 'linux'

    async def get_device_type_hostname(self):
        '''Determine the type of device we are talking to if using ssh/local'''

        devtype = 'Unknown'
        hostname = None
        # There isn't that much of a difference in running two commands versus
        # running them one after the other as this involves an additional ssh
        # setup time. show version works on most networking boxes and
        # hostnamectl on Linux systems. That's all we support today.
        if self.transport == 'local':
            output = await self.local_gather(['show version', 'hostnamectl',
                                              'goes show machine'])
        else:
            output = await asyncio.wait_for(
                self.ssh_gather(['show version', 'hostnamectl',
                                 'goes show machine']), timeout=5)

        if output[0]['status'] == 0:
            data = output[1]['data']
            if 'Arista ' in data:
                devtype = 'eos'
            elif 'JUNOS ' in data:
                devtype = 'junos'

            if self.transport == 'local':
                output = await self.local_gather(['show hostname'])
            else:
                output = await asyncio.wait_for(
                    self.ssh_gather(['show hostname']), timeout=5)
            if output[0]['status'] == 0:
                hostname = output[1]['data'].strip()

        elif output[1]['status'] == 0:
            data = output[1]['data']
            if 'Cumulus Linux' in data:
                devtype = 'cumulus'
            elif 'Ubuntu' in data:
                devtype = 'Ubuntu'
            elif 'Red Hat' in data:
                devtype = 'RedHat'
            elif 'Debian GNU/Linux' in data:
                devtype = 'Debian'
            else:
                devtype = 'linux'

            if output[2]['status'] == 0:
                devtype = 'platina'

            # Hostname is in the first line of hostnamectl
            hostline = data.splitlines()[0].strip()
            if hostline.startswith('Static hostname'):
                _, hostname = hostline.split(':')
                hostname = hostname.strip()

        self.devtype = devtype
        if hostname:
            self.hostname = hostname

    def get_status(self):
        return self.status

    def set_unreach_status(self):
        self.status = 'unreachable'

    def set_good_status(self):
        self.status = 'good'

    def is_alive(self):
        return self.status == 'good'

    async def set_hostname(self, hostname=None):
        '''This routine needs to be implemented by child class'''
        if hostname:
            self.hostname = hostname

    async def local_gather(self, cmd_list=None):
        '''Given a dictionary of commands, run locally and return outputs'''

        result = []
        for cmd in cmd_list:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=PIPE,
                                                         stderr=PIPE)

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(),
                                                        timeout=5)
                result.append({'status': proc.returncode,
                               'timestamp': int(time.time()*1000),
                               'cmd': cmd,
                               'devtype': self.devtype,
                               'datacenter': self.dcname,
                               'hostname': self.hostname,
                               'data': stdout.decode('ascii', 'ignore')
                               if not proc.returncode
                               else stderr.decode('ascii', 'ignore')})
            except asyncio.TimeoutError as e:
                    result.append({'status': 408,
                                   'timestamp': int(time.time()*1000),
                                   'cmd': cmd,
                                   'devtype': self.devtype,
                                   'datacenter': self.dcname,
                                   'hostname': self.hostname,
                                   'data': {'error': str(e)}})

        return result

    async def ssh_gather(self, cmd_list=None):
        '''Given a dictionary of commands, run ssh and return outputs'''

        result = []

        if cmd_list is None:
            return result
        try:
            conn = await asyncio.wait_for(
                asyncssh.connect(self.address, port=self.port,
                                 known_hosts=None, client_keys=self.pvtkey,
                                 username=self.username,
                                 password=self.password), timeout=5)
        except (asyncio.TimeoutError, ConnectionResetError, OSError,
                ConnectionRefusedError, asyncssh.misc.DisconnectError) as e:
            for cmd in cmd_list:
                logging.error('Unable to connect to node {}'.format(
                    self.hostname))
                result.append({'status': 408,
                               'timestamp': int(time.time()*1000),
                               'cmd': cmd,
                               'devtype': self.devtype,
                               'datacenter': self.dcname,
                               'hostname': self.hostname,
                               'data': {'error': str(e)}})
            return result

        if conn:
            for cmd in cmd_list:
                try:
                    output = await asyncio.wait_for(conn.run(cmd), timeout=5)
                    result.append({'status': output.exit_status,
                                   'timestamp': int(time.time()*1000),
                                   'cmd': cmd,
                                   'devtype': self.devtype,
                                   'datacenter': self.dcname,
                                   'hostname': self.hostname,
                                   'data': output.stdout})
                except (asyncio.TimeoutError, ConnectionResetError,
                        ConnectionRefusedError, OSError,
                        asyncssh.misc.DisconnectError) as e:
                    result.append({'status': 408,
                                   'timestamp': int(time.time()*1000),
                                   'cmd': cmd,
                                   'devtype': self.devtype,
                                   'datacenter': self.dcname,
                                   'hostname': self.hostname,
                                   'data': {'error': str(e)}})
                except asyncssh.misc.ChannelOpenError as e:
                    result.append({'status': 404,
                                   'timestamp': int(time.time()*1000),
                                   'cmd': cmd,
                                   'devtype': self.devtype,
                                   'datacenter': self.dcname,
                                   'hostname': self.hostname,
                                   'data': {'error': str(e)}})

            conn.close()
            conn.wait_closed()

        return result

    async def rest_gather(self, svc_dict, oformat='json'):
        raise NotImplementedError

    async def exec_cmd(self, cmd_list, oformat='json'):
        if self.transport == 'ssh':
            result = await self.ssh_gather(cmd_list)
        elif self.transport == 'https':
            result = await self.rest_gather(cmd_list, oformat)
        elif self.transport == 'local':
            result = await self.local_gather(cmd_list)
        else:
            logging.error('Unsupported transport {} for node {}'.format(
                self.transport, self.hostname))

        return result

    async def exec_service(self, svc_defn):

        result = []             # same type as gather function
        if not svc_defn:
            return result

        if self.status == 'init':
            if self.init_again_at < time.time():
                await self.init_node()

        if self.status == 'init':
            result.append({'status': 404,
                           'timestamp': int(time.time()*1000),
                           'devtype': self.devtype,
                           'datacenter': self.dcname,
                           'hostname': self.hostname,
                           'data': result})
            return result

        use = svc_defn.get(self.hostname, None)
        if not use:
            use = svc_defn.get(self.devtype, {})
        if not use:
            return result

        if 'copy' in use:
            use = svc_defn.get(use.get('copy'))

        if use:
            cmd = use.get('command', None)

        oformat = svc_defn.get(self.devtype, {}) \
                          .get('format', 'json')

        if not cmd:
            return result

        if type(cmd) is not list:
            cmd = [cmd]

        return await self.exec_cmd(cmd, oformat=oformat)


class EosNode(Node):
    def _init(self, **kwargs):
        super()._init(kwargs)
        self.devtype = 'eos'

    async def rest_gather(self, cmd_list=None, oformat='json'):

        result = []
        if not cmd_list:
            return result

        now = int(time.time()*1000)
        auth = aiohttp.BasicAuth(self.username, password=self.password)
        data = {"jsonrpc": "2.0", "method": "runCmds", "id": int(now),
                "params": {"version": 1, 'format': oformat,
                           "cmds": cmd_list}}
        headers = {'Content-Type': 'application/json'}
        if self.port:
            url = 'https://{}:{}/command-api'.format(self.address, self.port)
        else:
            url = 'https://{}:{}/command-api'.format(self.address, self.port)

        output = []
        status = 200            # status OK

        try:
            async with aiohttp.ClientSession(
                    auth=auth, conn_timeout=10, read_timeout=5,
                    connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.post(url,
                                        json=data,
                                        headers=headers) as response:
                    status, json_out = response.status, await response.json()
                    if 'result' in json_out:
                        output.append(json_out['result'][0])
                    else:
                        output.append(json_out['error'])

            for i, cmd in enumerate(cmd_list):
                result.append({
                    'status': status,
                    'timestamp': now,
                    'cmd': cmd,
                    'devtype': self.devtype,
                    'datacenter': self.dcname,
                    'hostname': self.hostname,
                    'data': output[i] if type(output) is list else output
                })
        except (asyncio.TimeoutError, OSError) as e:
            for cmd in cmd_list:
                result.append({'status': 408,
                               'timestamp': int(time.time()*1000),
                               'cmd': cmd,
                               'devtype': self.devtype,
                               'datacenter': self.dcname,
                               'hostname': self.hostname,
                               'data': {'error': str(e)}})

        return result

    async def set_hostname(self, hostname=None):
        if hostname:
            self.hostname = hostname
            return

        output = await self.exec_cmd(['show hostname'])

        if output and output[0]['status'] == 200:
            self.hostname = output[0]['data']['hostname']


class CumulusNode(Node):
    def _init(self, **kwargs):
        if 'username' not in kwargs:
            kwargs['username'] = 'cumulus'
        if 'password' not in kwargs:
            kwargs['password'] = 'CumulusLinux!'

        super()._init(kwargs)
        self.devtype = 'cumulus'

    async def rest_gather(self, cmd_list=None):

        result = []
        if not cmd_list:
            return result

        auth = aiohttp.BasicAuth(self.username, password=self.password)
        url = 'https://{0}:{1}/nclu/v1/rpc'.format(self.address, self.port)
        headers = {'Content-Type': 'application/json'}
        timeout = aiohttp.ClientTimeout(total=5)

        try:
            async with aiohttp.ClientSession(
                    auth=auth, conn_timeout=5, read_timeout=10,
                    connector=aiohttp.TCPConnector(ssl=False)) as session:
                for cmd in cmd_list:
                    data = {'cmd': cmd}
                    async with session.post(url, json=data,
                                            headers=headers) as response:
                        result.append({'status': response.status,
                                       'timestamp': int(time.time()*1000),
                                       'cmd': cmd,
                                       'devtype': self.devtype,
                                       'datacenter': self.dcname,
                                       'hostname': self.hostname,
                                       'data': await response.text()})
        except asyncio.TimeoutError as e:
            result.append({'status': 408,
                           'timestamp': int(time.time()*1000),
                           'cmd': cmd,
                           'devtype': self.devtype,
                           'datacenter': self.dcname,
                           'hostname': self.hostname,
                           'data': {'error': str(e)}})

        return result

        async def set_hostname(self, hostname=None):
            if hostname:
                self.hostname = hostname
                return

            output = await self.exec_cmd(['hostname'])

            if output and output[0]['status'] == 200:
                self.hostname = output[0]['data']['hostname']


class LinuxNode(Node):
    def _init(self, **kwargs):
        super()._init(kwargs)
        self.devtype = 'linux'

    async def set_hostname(self, hostname=None):
        if hostname:
            self.hostname = hostname
            return

        output = await self.exec_cmd(['hostname'])

        if output and output[0]['status'] == 200:
            self.hostname = output[0]['data']['hostname']

