import subprocess
import argparse
import yaml
from jsonschema import validate
from jsonschema.exceptions import ValidationError

schema = {
    "type": "object",
    "properties": {
        "devices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nos": {
                        "type": "string"
                    },
                    "version": {
                        "type": "string"
                    },
                    "hostname": {
                        "type": "string"
                    },
                    "ssh_port": {
                        "type": "integer"
                    },
                    "rest_port": {
                        "type": "integer"
                    },
                },
                "required": [
                    "nos", "version", "hostname"
                ]
            }
        }
    }
}


def run_simnodes(devices: list):
    """Start ssh and rest simnode subprocesses with the options
    (nos, version, hostname) given in the configuration file
    """
    processes = []
    for dev in devices:
        ssh_port = dev.get("ssh_port", 0)
        rest_port = dev.get("rest_port", 0)
        if ssh_port:
            cmd = [
                "python", "tests/utilities/simnode_ssh.py",
                "-n", dev["nos"],
                "-v", dev["version"],
                "-H", dev["hostname"],
                "-p", str(dev["ssh_port"])
                ]
            p = subprocess.Popen(cmd)
            print(
                "Running ssh node", dev["nos"],
                dev["version"], dev["hostname"])
            processes.append(p)

        if rest_port:
            cmd = [
                "python", "tests/utilities/simnode_rest.py",
                "-n", dev["nos"],
                "-v", dev["version"],
                "-H", dev["hostname"],
                "-p", str(rest_port)
                ]
            p = subprocess.Popen(cmd)
            print(
                "Running rest node", dev["nos"],
                dev["version"], dev["hostname"])
            processes.append(p)

    for p in processes:
        p.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-D", "--devices-file", type=str, help="Device list file")
    args = parser.parse_args()

    devs = {}

    with open(args.devices_file) as fh:
        devs = yaml.load(fh, Loader=yaml.FullLoader)

    try:
        validate(devs, schema)
    except ValidationError as e:
        print(e.message)
        exit(1)

    run_simnodes(devs["devices"])
