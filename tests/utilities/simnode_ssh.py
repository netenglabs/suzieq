import asyncio
import asyncssh
import sys
import os
import crypt
from importlib.util import find_spec


class MySSHServerSession(asyncssh.SSHServerSession):
    def __init__(self, device='iosxr'):
        self._input = ''
        self._data = None
        self.device = device
        self.run_as_shell = False
        self.prompt = '# '
        self.vendor = 'cisco'
        self.sample_data_dir = './tests/integration/nossim/'
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
        return False

    def get_cmd_file(self, command: str, fmt: str = '.txt') -> str:

        self.cmd_data = {
            'show version':
            f'{self.sample_data_dir}/{self.device}/show_version{fmt}',
            'show run hostname':
            f'{self.sample_data_dir}/{self.device}/show_run_hostname{fmt}',
            'show hostname':
            f'{self.sample_data_dir}/{self.device}/show_hostname{fmt}',
            'show interfaces':
            f'{self.sample_data_dir}/{self.device}/show_interfaces{fmt}',
            'show interface':
            f'{self.sample_data_dir}/{self.device}/show_interfaces{fmt}',
            'show ethernet-switching table detail':
            f'{self.sample_data_dir}/{self.device}/show_ethernet_switching_table{fmt}',
            'show system uptime':
            f'{self.sample_data_dir}/{self.device}/show_system_uptime{fmt}',
            'show mac-address table':
            f'{self.sample_data_dir}/{self.device}/show_mac_address_table{fmt}',
            'show ip arp':
            f'{self.sample_data_dir}/{self.device}/show_ip_arp{fmt}',
            'show ipv6 neighbors':
            f'{self.sample_data_dir}/{self.device}/show_ipv6_neighbors{fmt}',
            'show ip route vrf *':
            f'{self.sample_data_dir}/{self.device}/show_ip_route{fmt}',
            'show ipv6 route vrf *':
            f'{self.sample_data_dir}/{self.device}/show_ipv6_route{fmt}',
            'show bgp all neighbors':
            f'{self.sample_data_dir}/{self.device}/show_bgp_all_neighbors{fmt}',
            'show bgp all summary':
            f'{self.sample_data_dir}/{self.device}/show_bgp_all_summary{fmt}',
            'show inventory':
            f'{self.sample_data_dir}/{self.device}/show_inventory{fmt}',
            'show ip interfaces':
            f'{self.sample_data_dir}/{self.device}/show_ip_interfaces{fmt}',
            'show ipv6 interfaces':
            f'{self.sample_data_dir}/{self.device}/show_ipv6_interfaces{fmt}',
            'show vrf detail':
            f'{self.sample_data_dir}/{self.device}/show_vrf_detail{fmt}',
            'show chassis hardware':
            f'{self.sample_data_dir}/{self.device}/show_chassis_hardware{fmt}',
            'show interface trasnsceiver':
            f'{self.sample_data_dir}/{self.device}/show_interface_transceiver{fmt}',
            'show configuration routing-instances':
            f'{self.sample_data_dir}/{self.device}/show_configuration_routing_instances{fmt}',
            'show bridge mac-table':
            f'{self.sample_data_dir}/{self.device}/show_bridge_mac_table{fmt}',
            'cat /proc/uptime; hostnamectl; show version':
            f'{self.sample_data_dir}/{self.device}/device.txt',
            'ip route show table all':
            f'{self.sample_data_dir}/{self.device}/ip_route_show_table_all.txt',
        }

        return self.cmd_data.get(command, '')

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
            self._chan.write(self._data)
            self._chan.exit(0)
        elif not self.run_as_shell:
            self._chan.exit(1)
        elif self.run_as_shell:
            self._chan.write('Command not found\n')
            self._chan.write(f'{self.prompt}')


class MySSHServer(asyncssh.SSHServer):
    def __init__(self, device='iosxr'):
        self.passwords = {'vagrant': 'vaqRzE48Dulhs'}   # password of 'vagrant'
        self.device = device

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
        return MySSHServerSession(device=self.device)


class IOSXRServer(MySSHServer):
    def __init__(self):
        super().__init__(device='iosxr')


class IOSXEServer(MySSHServer):
    def __init__(self):
        super().__init__(device='iosxe')


class NXOSServer(MySSHServer):
    def __init__(self):
        super().__init__(device='nxos')


class EOSServer(MySSHServer):
    def __init__(self):
        super().__init__(device='eos')


class QFXServer(MySSHServer):
    def __init__(self):
        super().__init__(device='qfx')


class MXServer(MySSHServer):
    def __init__(self):
        super().__init__(device='mx')


class SRXServer(MySSHServer):
    def __init__(self):
        super().__init__(device='srx')


class SoNICServer(MySSHServer):
    def __init__(self):
        super().__init__(device='sonic')


async def start_server(device='iosxr'):
    factory = {
        'iosxr': IOSXRServer,
        'nxos': NXOSServer,
        'eos': EOSServer,
        'iosxe': IOSXEServer,
        'qfx': QFXServer,
        'mx': MXServer,
        'srx': SRXServer,
        'sonic': SoNICServer,
    }
    await asyncssh.listen('', 10000, server_factory=factory[device],
                          server_host_keys=['/home/ddutt/work/suzieq/play/ssh_host_key'])

if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(start_server(sys.argv[1]))
    except (OSError, asyncssh.Error) as exc:
        sys.exit('Error starting server: ' + str(exc))

    loop.run_forever()
