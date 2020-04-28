#!/usr/bin/env python3

import sys
import shlex


def process_ansible_inventory(filename, namespace='default'):
    """Read an Ansible inventory file and produce device list for suzieq

    :param filename: Ansible inventory filename
    :type filename: string

    :param namespace: The namespace associated with the data from these devices
    :type namespace: string

    :rtype: list:
    :return: List of devices as extracted from the Ansible file
    """

    with open(filename, 'r') as f:
        lines = f.readlines()

    hostsdata = []
    for line in lines:
        host = None
        hostline = ''
        out = shlex.split(line)
        if 'ansible_network_os=eos' in out:
            transport = 'https'
            addnl_info = 'devtype=eos'
        else:
            transport = 'ssh'
            addnl_info = ''
        for elem in out:
            if elem.startswith('ansible_host='):
                k, v = elem.split('=')

                if v == '127.0.0.1':
                    host = v
                    port = 0
                    continue
                else:
                    hostline = ('    - url: {}://vagrant@{} {}'
                                .format(transport, v, addnl_info))
            if elem.startswith('ansible_port='):
                k, v = elem.split('=')
                if host:
                    hostline = (
                        '    - url: ssh://vagrant@{}:{}'.format(host, v))

            if elem.startswith('ansible_ssh_private_key_file') and transport == 'ssh':
                k, v = elem.split('=')
                if hostline:
                    hostline += ' keyfile={}'.format(v.strip())
                else:
                    addnl_info += ' keyfile={}'.format(v.strip())

        hostsdata.append(hostline)

    hostsdata.insert(0, '- namespace: {}'.format(namespace))
    hostsdata.insert(1, '  hosts:')

    return hostsdata


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: genhosts <Ansible inventory file> <output file> <DC name>')
        sys.exit(1)

    hostsdata = process_ansible_inventory(sys.argv[1], sys.argv[3])

    out = '\n'.join(hostsdata)

    with open(sys.argv[2], 'w') as f:
        f.write(out)
