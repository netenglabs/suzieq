
from collections import defaultdict
import time
from ipaddress import ip_address

import asyncio
import asyncssh
import aiohttp


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

    async def ssh_gather(self, cmd_list=None):
        '''Given a dictionary of commands, run ssh and return outputs'''

        result = []

        if cmd_list is None:
            return result

        async with asyncssh.connect(self.address, port=self.port,
                                    known_hosts=None, client_keys=self.pvtkey,
                                    username=self.username,
                                    password=self.password) as conn:
            for cmd in cmd_list:
                output = await conn.run(cmd)
                result.append({'status': output.exit_status,
                               'timestamp': time.time(),
                               'cmd': cmd,
                               'devtype': self.devtype,
                               'datacenter': self.dcname,
                               'hostname': self.hostname,
                               'data': output.stdout})

        return result

    async def rest_gather(self, svc_dict):
        raise NotImplementedError

    async def exec_cmd(self, cmd_list):
        if self.transport == 'ssh':
            result = await self.ssh_gather(cmd_list)
        elif self.transport == 'https':
            result = await self.rest_gather(cmd_list)
        else:
            logging.error('Unsupported transport {} for node {}'.format(
                self.transport, self.hostname))

        return result

    async def exec_service(self, svc_defn):

        result = []             # same type as gather function
        if not svc_defn:
            return result

        cmd = svc_defn.get(self.devtype, {}) \
                      .get('command', None)

        if not cmd:
            return result

        return await self.exec_cmd([cmd])


class EosNode(Node):
    def __init__(self, **kwargs):
        super(EosNode).__init__(kwargs)
        self.devtype = 'eos'

    async def rest_gather(self, cmd_list=None):

        result = []
        if not cmd_list:
            return result

        now = time.time()
        auth = aiohttp.BasicAuth(self.username, password=self.password)
        data = {"jsonrpc": "2.0", "method": "runCmds", "id": int(now),
                "params": {"version": 1,
                           "cmds": cmd_list}}
        headers = {'Content-Type': 'application/json'}
        if self.port:
            url = 'https://{}:{}/command-api'.format(self.address, self.port)
        else:
            url = 'https://{}:{}/command-api'.format(self.address, self.port)

        output = []
        status = 200            # status OK

        async with aiohttp.ClientSession() as session:
            async with aiohttp.ClientSession(
                    auth=auth,
                    connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.post(url,
                                        json=data,
                                        headers=headers) as response:
                    status, json_out = response.status, await response.json()
                    if 'result' in json_out:
                        output.append(json_out['result'][0])
                    else:
                        output.append(json_out['error'][0])

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

        async with aiohttp.ClientSession(
                auth=auth,
                connector=aiohttp.TCPConnector(ssl=False)) as session:
            for cmd in cmd_list:
                data = {'cmd': cmd}
                async with session.post(url, json=data,
                                        headers=headers) as response:
                    result.append({'status': response.status,
                                   'timestamp': time.time(),
                                   'cmd': cmd,
                                   'devtype': self.devtype,
                                   'datacenter': self.dcname,
                                   'hostname': self.hostname,
                                   'data': await response.text()})

        return result


class LinuxNode(Node):
    def __init__(self, **kwargs):
        super(EosNode).__init__(kwargs)
        self.devtype = 'linux'
        self.transport = 'ssh'
