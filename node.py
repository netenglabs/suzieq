
from collections import defaultdict
import os
import time
from ipaddress import ip_address
import logging

import json
import yaml
from urllib.parse import urlparse

import asyncio
import asyncssh
import aiohttp
from asyncio.subprocess import PIPE


async def get_device_type_hostname(nodeobj):
    '''Determine the type of device we are talking to'''

    devtype = 'Unknown'
    hostname = 'localhost'
    # There isn't that much of a difference in running two commands versus
    # running them one after the other as this involves an additional ssh
    # setup time. show version works on most networking boxes and
    # hostnamectl on Linux systems. That's all we support today.
    if nodeobj.transport == 'local':
        output = await nodeobj.local_gather(['show version', 'hostnamectl'])
    else:
        output = await asyncio.wait_for(
            nodeobj.ssh_gather(['show version', 'hostnamectl']), timeout=5)

    if output[0]['status'] == 0:
        data = output[1]['data']
        if 'Arista ' in data:
            devtype = 'eos'
        elif 'JUNOS ' in data:
            devtype = 'junos'

        if nodeobj.transport == 'local':
            output = await nodeobj.local_gather(['show hostname'])
        else:
            output = await asyncio.wait_for(
                nodeobj.ssh_gather(['show hostname']), timeout=5)
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

        # Hostname is in the first line of hostnamectl
        hostline = data.splitlines()[0].strip()
        if hostline.startswith('Static hostname'):
            _, hostname = hostline.split(':')
            hostname = hostname.strip()

    return devtype, hostname


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
            hostsconf = yaml.load(f.read())
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
                password = result.password
                port = result.port
                host = result.hostname

                if password:
                    newnode = Node(hostname=host, username=username,
                                   password=password, transport=result.scheme,
                                   port=port, datacenter=dcname)
                else:
                    newnode = Node(hostname=host, username=username,
                                   transport=result.scheme, port=port,
                                   datacenter=dcname)

                devtype = None
                hostname = 'localhost'
                if result.scheme == 'ssh' or result.scheme == 'local':
                    devtype, hostname = await get_device_type_hostname(newnode)
                else:
                    if len(words) > 1:
                        try:
                            devtype = words[1].split('=')[1]
                        except IndexError:
                            logging.error(
                                "Unable to determine device type for {}"
                                .format(host))
                            continue

                if devtype is None:
                    logging.error('Unable to determine device type for {}'
                                  .format(host))
                    continue

                if devtype == 'cumulus':
                    newnode.__class__ = CumulusNode
                    newnode.devtype = devtype
                elif devtype == 'eos':
                    newnode.__class__ = EosNode
                    newnode.devtype = devtype
                    output = await newnode.rest_gather(['show hostname'])

                    if output and output[0]['status'] == 200:
                        hostname = output[0]['data']['hostname']

                elif any(n == devtype for n in ['Ubuntu', 'Debian',
                                                'Red Hat', 'Linux']):
                    newnode.__class__ = LinuxNode
                    newnode.devtype = 'linux'

                newnode.hostname = hostname

                logging.info('Added node {}'.format(hostname))
                if newnode:
                    nodes.update({hostname: newnode})

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

    def __init__(self, **kwargs):
        if not kwargs:
            raise ValueError

        self.hostname = kwargs['hostname']  # Mandatory parameter
        self.username = kwargs.get('username', 'vagrant')
        self.password = kwargs.get('password', 'vagrant')
        self.transport = kwargs.get('transport', 'ssh')
        self.address = kwargs.get('address', self.hostname)
        self.dcname = kwargs.get('datacenter', "default")
        self.port = kwargs.get('port', 0)
        pvtkey_file = kwargs.get('pvtkey_file', None)
        if pvtkey_file:
            self.pvtkey = asyncssh.public_key.read_private_key(pvtkey_file)

        if not self.port:
            if self.transport == 'ssh':
                self.port = 22
            elif self.transport == 'https':
                self.port = 443

    def get_status(self):
        return self.status

    def is_alive(self):
        return self.status == 'good'

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
        except asyncio.TimeoutError as e:
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
                except asyncio.TimeoutError as e:
                    result.append({'status': 408,
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

        return await self.exec_cmd([cmd], oformat=oformat)


class EosNode(Node):
    def __init__(self, **kwargs):
        super(EosNode).__init__(kwargs)
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
        except asyncio.TimeoutError as e:
            for cmd in cmd_list:
                result.append({'status': 408,
                               'timestamp': int(time.time()*1000),
                               'cmd': cmd,
                               'devtype': self.devtype,
                               'datacenter': self.dcname,
                               'hostname': self.hostname,
                               'data': {'error': str(e)}})

        return result


class CumulusNode(Node):
    def __init__(self, **kwargs):
        if 'username' not in kwargs:
            kwargs['username'] = 'cumulus'
        if 'password' not in kwargs:
            kwargs['password'] = 'CumulusLinux!'

        super(EosNode).__init__(kwargs)
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


class LinuxNode(Node):
    def __init__(self, **kwargs):
        super(LinuxNode).__init__(kwargs)
        self.devtype = 'linux'
