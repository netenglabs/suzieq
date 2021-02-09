#!/usr/bin/env python3

import sys
import shlex
import yaml
from os.path import exists


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
                    continue
                else:
                    hostline = ('    - url: {}://vagrant@{} {}'
                                .format(transport, v, addnl_info))
            if elem.startswith('ansible_port='):
                k, v = elem.split('=')
                if host:
                    hostline = (
                        '    - url: ssh://vagrant@{}:{}'.format(host, v))

            if elem.startswith('ansible_ssh_private_key_file'):
                k, v = elem.split('=')
                if not exists(v.strip()):
                    continue
                if hostline:
                    hostline += ' keyfile={}'.format(v.strip())
                else:
                    addnl_info += ' keyfile={}'.format(v.strip())

        hostsdata.append(hostline)

    hostsdata.insert(0, '- namespace: {}'.format(namespace))
    hostsdata.insert(1, '  hosts:')

    return hostsdata


def convert_ansible_inventory(filename: str, namespace: str = 'default'):
    """Converts the output of ansible-inventory command for processing.

    Ansible pulls together the inventory information from multiple files. The
    information relevant to sq-poller maybe present in different files as
    different vars. ansible-invenoty command luckily handles this for us. This
    function takes the JSON output of that command and gathers the data needed
    to start polling.

    Parameters
    ----------
    :pararm filename: file containing the output of ansible-inventory output
    :type filename" string

    :param namespace: namespace associated with this inventory
    :type namespace: string

    Returns
    -------
    :rtype: list
    :return: List of devices and the related info to connect
    """

    try:
        with open(filename, 'r') as f:
            inventory = yaml.safe_load(f)
    except Exception as error:
        print(f':ERROR: Unable to process Ansible inventory: {str(error)}')
        sys.exit(1)

    if '_meta' not in inventory or "hostvars" not in inventory['_meta']:
        if isinstance(inventory, list) and 'namespace' in inventory[0]:
            print("ERROR: Invalid Ansible inventory, found Suzieq inventory, "
                  "use -D option")
        else:
            print("ERROR: Invalid Ansible inventory, "
                  "missing keys: _meta and / or hostvars\n"
                  "\tUse 'ansible-inventory --list' to create the correct file")
        sys.exit(1)

    in_hosts = inventory['_meta']['hostvars']
    out_hosts = []
    for host in in_hosts:
        entry = in_hosts[host]
        addnl_info = ''

        addnl_info += f'username={entry["ansible_user"]} '
        if 'ansible_password' in entry:
            addnl_info += f' password={entry["ansible_password"]} '
        if entry.get('ansible_network_os', '') == 'eos':
            transport = 'https://'
            addnl_info += 'devtype=eos'
            port = 443
        else:
            transport = 'ssh://'
            port = entry["ansible_port"]

        url = (f'{transport}{entry["ansible_host"]}'
               f':{port}')
        keyfile = entry.get('ansible_ssh_private_key_file', '')
        if keyfile:
            if exists(keyfile.strip()):
                hostline = f'    - url: {url} keyfile={keyfile} {addnl_info}'
            else:
                hostline = f'    - url: {url} {addnl_info}'
        else:
            hostline = f'    - url: {url} {addnl_info}'

        out_hosts.append(hostline)

    out_hosts.insert(0, '- namespace: {}'.format(namespace))
    out_hosts.insert(1, '  hosts:')

    return out_hosts


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: genhosts <Ansible inventory file> <output file> <DC name>')
        sys.exit(1)

    hostsdata = convert_ansible_inventory(sys.argv[1], sys.argv[3])

    out = '\n'.join(hostsdata)

    with open(sys.argv[2], 'w') as f:
        f.write(out)
