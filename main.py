import sys
import os
import argparse
import asyncio
import logging
from pathlib import Path

import json
import yaml
from urllib.parse import urlparse

from Node import Node, CumulusNode, EosNode, LinuxNode
from service import Service, InterfaceService, SystemService

async def get_device_type_hostname(nodeobj):
    '''Determine the type of device we are talking to'''

    devtype = 'Unknown'
    hostname = 'localhost'
    # There isn't that much of a difference in running two commands versus
    # running them one after the other as this involves an additional ssh
    # setup time. show version works on most networking boxes and
    # hostnamectl on Linux systems. That's all we support today.
    output = await nodeobj.ssh_gather(['show version', 'hostnamectl'])

    if output[0]['status'] == 0:
        if 'Arista ' in output[0]['data']:
            devtype = 'eos'
        elif 'JUNOS ' in output[0]['data']:
            devtype = 'junos'

        output = await nodeobj.ssh_gather(['show hostname'])
        if output[0]['status'] == 0:
            hostname = output[0]['data']

    elif output[1]['status'] == 0:
            if 'Cumulus Linux' in output[1]['data']:
                devtype = 'cumulus'
            elif 'Ubuntu' in output[1]['data']:
                devtype = 'Ubuntu'
            elif 'Red Hat' in output[1]['data']:
                devtype = 'RedHat'

            # Hostname is in the first line of hostnamectl
            hostline = output[1]['data'].splitlines()[0].strip()
            if hostline.startswith('Static hostname'):
                _, hostname = hostline.split(':')
                hostname = hostname.strip()

    return devtype, hostname


async def process_hosts(hosts_file, output_dir):
    '''Process list oof hosts
    This involves creating a node for each host listed, firing up services
    for which we need to pull data.'''

    nodes = {}

    if not os.path.isfile(hosts_file):
        logging.error('hosts config must be a file: {}', hosts_file)
        return nodes

    if not os.access(hosts_file, os.R_OK):
        logging.error('hosts config file is not readable: {}', hosts_file)
        return nodes

    with open(hosts_file, 'r') as f:
        try:
            hostsconf = yaml.load(f.read())
        except Exception as e:
            logging.error('Invalid hosts config file:{}', e)
            print('Invalid hosts config file:{}', e)
            sys.exit(1)

    for datacenter in hostsconf:
        if 'datacenter' not in datacenter:
            logging.warning('No datacenter specified, assuming "default"')
            dcname = "default"
        else:
            dcname = datacenter['datacenter']

        dcdir = '{}/{}'.format(output_dir, dcname)
        if not os.path.exists(dcdir):
            os.makedirs(dcdir)
        elif not os.path.isdir(dcdir):
            logging.error('{} MUST be a directory'.format(dcdir))
            sys.exit(1)

        for host in datacenter.get('hosts', None):
            entry = host.get('url', None)
            if entry:
                words = entry.split()
                result = urlparse(words[0])

                username = result.username
                password = result.password
                port = result.port
                host = result.hostname

                if password:
                    newnode = Node(hostname=host, username=username,
                                   password=password, transport=result.scheme,
                                   port=port, datacenter=dcname)
                else:
                    newnode = Node(hostname=host, username=username,
                                   transport=result.scheme, port=port,
                                   datacenter=dcname)

                devtype = None
                hostname = 'localhost'
                if result.scheme == 'ssh':
                    devtype, hostname = await get_device_type_hostname(newnode)
                else:
                    if len(words) > 1:
                        try:
                            devtype = words[1].split('=')[1]
                        except IndexError:
                            logging.error(
                                "Unable to determine device type for {}"
                                .format(host))
                            continue

                if devtype is None:
                    logging.error('Unable to determine device type for {}'
                                  .format(host))
                    continue

                if devtype == 'cumulus':
                    newnode.__class__ = CumulusNode
                elif devtype == 'eos':
                    newnode.__class__ = EosNode
                    output = await newnode.rest_gather(['show hostname'])

                    if output and output[0]['status'] == 200:
                        hostname = output[0]['data']['hostname']

                elif devtype == 'Ubuntu' or devtype == 'Red Hat':
                    newnode.__class__ = LinuxNode

                newnode.devtype = devtype
                newnode.hostname = hostname

                print('Added node {}'.format(hostname))
                if newnode:
                    nodes.update({hostname: newnode})

    return nodes


async def process_services(svc_dir, output_dir):
    '''Process service definitions by reading each file in svc dir'''

    svcs_list = []
    if not os.path.isdir(svc_dir):
        logging.error('services directory not a directory: {}', svc_dir)
        return svcs_list

    for root, dirnames, filenames in os.walk(svc_dir):
        for filename in filenames:
            if filename.endswith('yml') or filename.endswith('yaml'):
                with open(root + '/' + filename, 'r') as f:
                    svc_def = yaml.load(f.read())
                if 'service' not in svc_def or 'apply' not in svc_def:
                    logging.error('Ignorning invalid service file definition. \
                    Need both "service" and "apply" keywords: {}'
                                  .format(filename))
                    continue
                for elem, val in svc_def['apply'].items():
                    if ('command' not in val or
                            ('normalize' not in val and 'textfsm' not in val)):
                        logging.error('Ignorning invalid service file definition. \
                        Need both "command" and "normalize/textfsm" keywords:'
                                      '{}, {}'.format(filename, val))
                        continue

                # Valid service definition, add it to list
                if svc_def['service'] == 'interfaces':
                    service = InterfaceService(svc_def['service'],
                                               svc_def['apply'],
                                               svc_def.get('keys', []),
                                               svc_def.get('ignore-fields',
                                                           []), output_dir)
                elif svc_def['service'] == 'system':
                    service = SystemService(svc_def['service'],
                                            svc_def['apply'],
                                            svc_def.get('keys', []),
                                            svc_def.get('ignore-fields',
                                                        []), output_dir)
                else:
                    service = Service(svc_def['service'], svc_def['apply'],
                                      svc_def.get('keys', []),
                                      svc_def.get('ignore-fields', []),
                                      output_dir)

                print('Service {} added'.format(service.name))
                svcs_list.append(service)

    return svcs_list

if __name__ == '__main__':

    homedir = str(Path.home())
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hosts-file', type=str,
                        default='{}/{}'.format(homedir, 'suzieq-hosts.yml'),
                        help='FIle containing URL of hosts to observe')
    parser.add_argument('-p', '--password-file', type=str,
                        default='{}/{}'.format(homedir, 'suzieq-pwd.yml'),
                        help='FIle containing passwords')
    parser.add_argument('-s', '--service-dir', type=str, default='.',
                        help='Directory containing services definition')
    parser.add_argument('-o', '--output-dir', type=str,
                        default='/tmp/parquet-out',
                        help='FIle containing passwords')
    parser.add_argument('-l', '--log', type=str, default='WARNING',
                        choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'],
                        help='Logging message level, default is WARNING')
    parser.add_argument('-S', '--service-only', type=str,
                        help='Only run this comma separated list of services')

    userargs = parser.parse_args()

    logging.basicConfig(filename='/tmp/suzieq.log',
                        level=getattr(logging, userargs.log.upper()))

    if not os.path.exists(userargs.output_dir):
        os.makedirs(userargs.output_dir)

    elif not os.path.isdir(userargs.output_dir):
        logging.error('Output directory {} is not a directory'
                      .format(userargs.output_dir))
        sys.exit(1)

    loop = asyncio.get_event_loop()
    tasks = [process_hosts(userargs.hosts_file, userargs.output_dir),
             process_services(userargs.service_dir, userargs.output_dir)]

    nodes, svcs = loop.run_until_complete(asyncio.gather(*tasks))

    for svc in svcs:
        svc.set_nodes(nodes)

    logging.info('Suzieq Started')

    if userargs.service_only:
        svclist = userargs.service_only.split(',')
    else:
        svclist = [svc.name for svc in svcs]

    working_svcs = [svc for svc in svcs if svc.name in svclist]

    try:
        tasks = [svc.run() for svc in working_svcs]
        loop.run_until_complete(asyncio.gather(*tasks))
        # loop.run_until_complete(svcs[2].run())
    except KeyboardInterrupt:
        logging.info('Received keyboard interrupt. Terminating')
        loop.close()
        sys.exit(0)


