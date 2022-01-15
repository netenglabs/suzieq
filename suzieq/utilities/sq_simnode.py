'''
Device simulator that serves up fake SSH/REST server

The command outputs are reflected from files with the appropriate
command name and format extension. show_lldp_neighbors_detail.txt,
for example
'''
import sys
import subprocess
import argparse
from pathlib import Path

import yaml
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from suzieq.shared.utils import get_sq_install_dir

schema = {
    "type": "object",
    "properties": {
        "devices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "input-dir": {
                        "type": "string"
                    },
                    "hostname": {
                        "type": "string"
                    },
                    "ssh-port": {
                        "type": "integer"
                    },
                    "rest-port": {
                        "type": "integer"
                    },
                },
                "required": [
                    "input-dir", "hostname"
                ]
            }
        }
    }
}


# pylint: disable=redefined-outer-name
def run_simnodes(devices: list = None, input_dir: str = None,
                 port: int = None, transport: str = None):
    """Start ssh and rest simnode subprocesses with the options
    (nos, version, hostname) given in the configuration file
    """
    processes = []

    for dev in devices:
        topdir = Path(dev['input-dir'])
        if not topdir.exists():
            print(f'ERROR: Unable to find datadir {input_dir}')
            sys.exit(1)

        if dev.get('hostname', '') == "all":
            hostdirs = [x for x in topdir.iterdir() if x.is_dir()]
        else:
            hostdirs = [Path(topdir) / dev['hostname']]

        ssh_port = dev.get("ssh-port", 0)
        rest_port = dev.get("rest-port", 0)

        processes += run_simnodes_dir(hostdirs, ssh_port, rest_port)

    if input_dir:
        hostdirs = [x for x in input_dir.iterdir() if x.is_dir()]
        if transport == "ssh":
            ssh_port = port
            rest_port = 0
        else:
            rest_port = port
            ssh_port = 0

        processes += run_simnodes_dir(hostdirs, ssh_port, rest_port)

    for proc in processes:
        proc.wait()


def run_simnodes_dir(hostdirs: str, base_ssh_port: int,
                     base_rest_port: int) -> list:
    '''Run one or more sessions given the dir and port'''
    processes = []

    bindir = f'{get_sq_install_dir()}/utilities'

    for i, hostd in enumerate(sorted(hostdirs)):
        if base_ssh_port:
            ssh_port = base_ssh_port + i
            cmd = [
                "python", f"{bindir}/sq_simnode_ssh.py",
                "-p", str(ssh_port),
                "-d", hostd,
            ]
            # pylint: disable=consider-using-with
            proc = subprocess.Popen(cmd)
            print(
                f'Running ssh node with input dir {hostd} '
                f'for {hostd.parts[-1]} on port {ssh_port}')
            processes.append(proc)

        if base_rest_port:
            rest_port = base_rest_port + i
            cmd = [
                "python", f"{bindir}/sq_simnode_rest.py",
                "-p", str(rest_port),
                "-d", hostd,
            ]
            # pylint: disable=consider-using-with
            proc = subprocess.Popen(cmd)
            print(
                f'Running REST node with input dir {hostd} '
                f'for {hostd.parts[-1]} on port {rest_port}')

            processes.append(proc)

    return processes


def simnodes_main():
    '''The main routine'''
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "-D", "--devices-file", type=str, help="Device list file",
    )
    inputs.add_argument(
        "-i", "--input-dir", type=str, help="Directory containing host files"
    )
    parser.add_argument(
        "-p", "--port", type=int, help="Starting port to listen on",
        default=10000
    )
    parser.add_argument(
        "-t", "--transport", type=str, help="Starting port to listen on",
        default="ssh", choices=["ssh", "rest"]
    )

    args = parser.parse_args()

    devs = {}

    if args.devices_file:
        with open(args.devices_file, encoding='utf8') as fh:
            devs = yaml.load(fh, Loader=yaml.FullLoader)

        try:
            validate(devs, schema)
        except ValidationError as e:
            print(e.message)
            sys.exit(1)
    else:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f'ERROR: Input dir {args.input_dir} does not exist')
            sys.exit(1)
        if not input_dir.is_dir():
            print(f'ERROR: Input dir {args.input_dir} is not a dir')
            sys.exit(1)

    run_simnodes(devs, input_dir=input_dir, port=args.port,
                 transport=args.transport)


if __name__ == '__main__':
    simnodes_main()
