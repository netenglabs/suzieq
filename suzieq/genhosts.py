#!/usr/bin/env python3

import sys
import shlex

if len(sys.argv) < 4:
    print('Usage: genhosts <Ansible inventory file> <output file> <DC name>')
    sys.exit(1)

with open(sys.argv[1], 'r') as f:
    lines = f.readlines()

hostsdata = []
for line in lines:
    host = None
    out = shlex.split(line)
    for elem in out:
        if elem.startswith('ansible_host='):
            k, v = elem.split('=')

            if v == '127.0.0.1':
                host = v
                port = 0
                continue
            else:
                hostsdata.append('    - url: ssh://vagrant@{}'.format(v))
                break
        if elem.startswith('ansible_port='):
            k, v = elem.split('=')
            if host:
                hostsdata.append('    - url: ssh://vagrant@{}:{}'.format(host, v))
                break

hostsdata.insert(0, '- datacenter: {}'.format(sys.argv[3]))
hostsdata.insert(1, '  hosts:')
out = '\n'.join(hostsdata)
with open(sys.argv[2], 'w') as f:
    f.write(out)
