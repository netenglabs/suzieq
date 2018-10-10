
import sys
import os
import argparse
import asyncio
import logging
from pathlib import Path

from node import init_hosts
from service import init_services


if __name__ == '__main__':

    homedir = str(Path.home())
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hosts-file', type=str,
                        default='{}/{}'.format(homedir, 'suzieq-hosts.yml'),
                        help='FIle with URL of hosts to observe')
    parser.add_argument('-P', '--password-file', type=str,
                        default='{}/{}'.format(homedir, 'suzieq-pwd.yml'),
                        help='FIle with passwords')
    parser.add_argument('-S', '--service-dir', type=str, required=True,
                        help='Directory with services definitions')
    parser.add_argument('-T', '--schema-dir', type=str, default='',
                        help='Directory with schema definition for services')
    parser.add_argument('-O', '--output-dir', type=str,
                        default='/tmp/parquet-out',
                        help='Directory to store parquet output in')
    parser.add_argument('-l', '--log', type=str, default='WARNING',
                        choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'],
                        help='Logging message level, default is WARNING')
    parser.add_argument('-s', '--service-only', type=str,
                        help='Only run this comma separated list of services')

    userargs = parser.parse_args()

    logging.basicConfig(filename='/tmp/suzieq.log',
                        level=getattr(logging, userargs.log.upper()),
                        format='%(asctime)s - %(name)s - %(levelname)s'
                        '- %(message)s')

    logger = logging.getLogger('suzieq')

    if not os.path.exists(userargs.output_dir):
        os.makedirs(userargs.output_dir)

    if not os.path.exists(userargs.service_dir):
        logger.error('Service directory {} is not a directory'.format(
            userargs.output_dir))
        print('Service directory {} is not a directory'.format(
            userargs.output_dir))
        sys.exit(1)

    elif not os.path.isdir(userargs.output_dir):
        logger.error('Output directory {} is not a directory'.format(
            userargs.output_dir))
        print('Output directory {} is not a directory'.format(
            userargs.output_dir))
        sys.exit(1)

    if not userargs.schema_dir:
        userargs.schema_dir = '{}/{}'.format(userargs.service_dir, 'schema')

    loop = asyncio.get_event_loop()
    tasks = [init_hosts(userargs.hosts_file, userargs.output_dir),
             init_services(userargs.service_dir, userargs.schema_dir,
                           userargs.output_dir)]

    nodes, svcs = loop.run_until_complete(asyncio.gather(*tasks))

    for svc in svcs:
        svc.set_nodes(nodes)

    logger.info('Suzieq Started')

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
        logger.info('Received keyboard interrupt. Terminating')
        loop.close()
        sys.exit(0)


