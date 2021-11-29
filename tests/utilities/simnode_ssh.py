import asyncio
import asyncssh
import sys
import os
import crypt
from importlib.util import find_spec
import argparse


class MySSHServerSession(asyncssh.SSHServerSession):
    def __init__(self, nos='iosxr', version='default', hostname='default'):
        self._input = ''
        self._data = None
        self.nos = nos
        self.nos_version = version
        self.hostname = hostname
        self.run_as_shell = False
        self.prompt = '# '
        self.vendor = 'cisco'
        self.sample_data_dir = './tests/integration/nossim'
        self._status = 0

    def get_testinput_dir(self):
        '''Get the dir where the test input data is stored'''
        return(os.path.dirname(find_spec('suzieq').loader.path) +
               '/../tests/integration/nossim')

    def connection_made(self, chan):
        self._chan = chan

    def shell_requested(self):
        self.run_as_shell = True
        return True

    def eof_received(self):
        self._chan.write('Goodbye!\n')
        self._chan.exit(0)

    def get_cmd_file(self, command: str, fmt: str = '.txt') -> str:

        if command:
            if command == 'cat /proc/uptime; hostnamectl; show version':
                return f'{self.sample_data_dir}/{self.nos}' \
                    f'/{self.nos_version}/{self.hostname}/nos.txt'

            cmdfile = command.replace("*", "all").replace(" ", "_") \
                .replace("-", "_")

            filepath = f'{self.sample_data_dir}/{self.nos}/' \
                f'{self.nos_version}/{self.hostname}/{cmdfile}{fmt}'

            if os.path.exists(filepath):
                return filepath

    def _exec_cmd(self, command):
        '''The routine to execute command and return data'''
        data = 'Command not found\n'
        if command in ['exit', 'quit']:
            self.eof_received()
            return ''
        if 'json' in command:
            command = command.split('|')[0].strip()
            fmt = '.json'
        else:
            fmt = '.txt'
        cmdfile = self.get_cmd_file(command, fmt)
        if cmdfile:
            with open(cmdfile, 'r') as f:
                data = f.read()
            self._status = 0
        else:
            self._status = -1
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
        if self._status == 0:
            if self._data is not None:
                self._chan.write(self._data)
            else:
                self._chan.write(f'{self.prompt}')
            if not self.run_as_shell:
                self._chan.exit(0)
        elif not self.run_as_shell:
            self._chan.exit(1)
        elif self.run_as_shell:
            self._chan.write('Command not found\n')
            self._chan.write(f'{self.prompt}')


class MySSHServer(asyncssh.SSHServer):
    def __init__(self, nos='iosxr', version="default", hostname="default"):
        self.passwords = {'vagrant': 'vaqRzE48Dulhs'}   # password of 'vagrant'
        self.nos = nos
        self.version = version
        self.hostname = hostname

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
        return MySSHServerSession(
            nos=self.nos, version=self.version, hostname=self.hostname)


async def start_server(
            port=10000, nos='iosxr', version="default", hostname="default"):

    await asyncssh.listen(
        '', port, server_factory=lambda: MySSHServer(nos, version, hostname),
        server_host_keys=['tests/integration/nossim/ssh_insecure_key'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n", "--nos", type=str, default="iosxr",
        help="NOS name (default: iosxr)")
    parser.add_argument(
        "-v", "--nos-version", type=str, help="NOS version",
        default="default")
    parser.add_argument(
        "-H", "--hostname", type=str, help="Hostname of the device",
        default="default")
    parser.add_argument(
        "-p", "--listening-port", type=int, default=10000,
        help="Listening port of the ssh server (default: 10000)")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(start_server(
            port=args.listening_port,
            nos=args.nos,
            version=args.nos_version,
            hostname=args.hostname)
            )
    except (OSError, asyncssh.Error) as exc:
        sys.exit('Error starting server: ' + str(exc))

    loop.run_forever()
