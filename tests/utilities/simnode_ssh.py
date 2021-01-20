import asyncio
import asyncssh
import sys
import os
import crypt
from importlib.util import find_spec


class MySSHServerSession(asyncssh.SSHServerSession):
    def __init__(self):
        self._input = ''
        self._data = None
        self.devtype = 'iosxr'
        self.run_as_shell = False
        self.prompt = '#'
        self.vendor = 'cisco'
        self.sample_data_dir = self.get_testinput_dir()
        self.cmd_data = {
            'show version':
            f'{self.sample_data_dir}/cisco/iosxr/show_version.txt',
            'show run hostname':
            f'{self.sample_data_dir}/cisco/iosxr/show_run_hostname.txt',
            'show interfaces':
            f'{self.sample_data_dir}/cisco/iosxr/show_interfaces.txt',
        }

    def get_testinput_dir(self):
        '''Get the dir where the test input data is stored'''
        return(os.path.dirname(find_spec('suzieq').loader.path) +
               '/../tests/integration/nossim')

    def connection_made(self, chan):
        self._chan = chan

    def shell_requested(self):
        self.run_as_shell = True
        return True

    def _exec_cmd(self, command):
        '''The routine to execute command and return data'''
        data = 'Command not found\n'
        if command in ['exit', 'quit']:
            self.eof_received()
            return ''
        if command in self.cmd_data:
            with open(self.cmd_data[command], 'r') as f:
                data = f.read()

        return data

    def exec_requested(self, command):
        '''Return the data for the specified command is possible'''

        self.run_as_shell = False
        command = command.rstrip('\n')
        self._data = self._exec_cmd(command)
        return True

    def data_received(self, input, datatype):
        '''Shell handler'''

        command = input.rstrip('\n')
        data = self._exec_cmd(command)
        self._chan.write(data)
        self._chan.write(self.prompt)

    def session_started(self):
        if self._data:
            self._chan.write(self._data)
            self._chan.exit(0)
        elif not self.run_as_shell:
            self._chan.exit(1)
        elif self.run_as_shell:
            self._chan.write(f'{self.prompt}')


class MySSHServer(asyncssh.SSHServer):
    def __init__(self):
        self.passwords = {'vagrant': 'vaqRzE48Dulhs'}   # password of 'vagrant'

    def connection_made(self, conn):
        print('SSH connection received from %s.' %
              conn.get_extra_info('peername')[0])

    def connection_lost(self, exc):
        if exc:
            print('SSH connection error: ' + str(exc), file=sys.stderr)
        else:
            print('SSH connection closed.')

    def begin_auth(self, username):
        # If the user's password is the empty string, no auth is required
        return self.passwords.get(username) != ''

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        pw = self.passwords.get(username, '*')
        return crypt.crypt(password, pw) == pw

    def session_requested(self):
        return MySSHServerSession()


async def start_server():
    await asyncssh.listen('', 10000, server_factory=MySSHServer,
                          server_host_keys=['/tmp/ssh_host_key'])

loop = asyncio.get_event_loop()

try:
    loop.run_until_complete(start_server())
except (OSError, asyncssh.Error) as exc:
    sys.exit('Error starting server: ' + str(exc))

loop.run_forever()
