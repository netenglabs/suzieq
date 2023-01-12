'''
Serve up a fake SSH server acting as device CLI
'''
import sys
import argparse
from pathlib import Path
import crypt

import asyncio
import asyncssh

from suzieq.shared.utils import get_sq_install_dir


class MySSHServerSession(asyncssh.SSHServerSession):
    '''Customised ssh server session for serving precanned outputs'''

    def __init__(self, input_dir: str = None):
        self._input = ''
        self._data = None
        self.input_dir = Path(f'{input_dir}')
        self.run_as_shell = False
        self.prompt = '# '
        self._status = 0
        self._chan = None

    def connection_made(self, chan):
        '''callback when connection is estd'''
        self._chan = chan

    def shell_requested(self):
        '''returns True if ssh client requested shell'''
        self.run_as_shell = True
        return True

    def eof_received(self):
        '''EOF received, end'''
        self._chan.write('Goodbye!\n')
        self._chan.exit(0)

    def get_cmd_file(self, command: str, fmt: str = '.txt') -> str:
        '''Return the file containing the output of the requested cmd'''

        if command:
            if command == 'cat /proc/uptime; hostnamectl; show version':
                return f'{self.input_dir}/nos.txt'

            cmdfile = command.replace("*", "all").replace(" ", "_")

            filepath = self.input_dir / f'{cmdfile}{fmt}'

            if filepath.exists():
                return filepath

            if command.find('exclude security') > 0:
                command = command.replace('exclude security', '').strip()

                cmdfile = command.replace("*", "all").replace(" ", "_")

                filepath = self.input_dir / f'{cmdfile}{fmt}'

                if filepath.exists():
                    return filepath

            print(f'File {filepath} not found')
            return ''

        return ''

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
            with open(cmdfile, 'r', encoding='utf8') as fhndl:
                data = fhndl.read()
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

    def data_received(self, data, datatype):
        '''Shell handler'''

        command = data.rstrip('\n')
        indata = self._exec_cmd(command)
        self._chan.write(indata)
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
    '''My own customized SSH server class to serve precanned outputs'''

    def __init__(self, input_dir: str = ''):
        self.passwords = {'vagrant': 'vaqRzE48Dulhs'}   # password of 'vagrant'
        self.input_dir = input_dir
        if not Path(f'{input_dir}').exists():
            print('ERROR: Received non-existent files dir '
                  f'{input_dir}')

    def connection_made(self, conn):
        '''Callback when connection is estd'''
        print('SSH connection received from '
              f'{conn.get_extra_info("peername")[0]}')

    # pylint: disable=redefined-outer-name
    def connection_lost(self, exc):
        '''Callback on losing client connection'''
        if exc:
            print('SSH connection error: ' + str(exc), file=sys.stderr)
        else:
            print('SSH connection closed.')

    def begin_auth(self, username):
        '''Start authorization'''
        # If the user's password is the empty string, no auth is required
        return self.passwords.get(username) != ''

    def password_auth_supported(self):
        '''Do we support password-based auth'''
        return True

    def validate_password(self, username, password):
        '''check if password is correct'''
        passwd = self.passwords.get(username, '*')
        return crypt.crypt(password, passwd) == passwd

    def session_requested(self):
        '''return new SSH session'''
        return MySSHServerSession(input_dir=self.input_dir)


async def start_server(port=10000, input_dir: str = None):
    """Run sim ssh server using the files in the given dir"""

    keyfile = Path(get_sq_install_dir()) / 'config/etc' / 'ssh_insecure_key'
    await asyncssh.listen(
        '127.0.0.1', port,
        server_factory=lambda: MySSHServer(input_dir=input_dir),
        server_host_keys=[keyfile])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--listening-port", type=int, default=10000,
        help="Listening port of the ssh server (default: 10000)")
    parser.add_argument(
        "-d", "--input-dir", type=str, default=None,
        help="Input dir to search for host files")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    if not Path(args.input_dir).exists():
        print(f'ERROR: Path {args.input_dir} does not exist, aborting')
        sys.exit(1)

    try:
        loop.run_until_complete(start_server(
            port=args.listening_port, input_dir=args.input_dir)
        )
    except (OSError, asyncssh.Error) as exc:
        sys.exit('Error starting server: ' + str(exc))

    loop.run_forever()
