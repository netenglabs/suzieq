
import sys
import os
import argparse
import asyncio
import logging
from pathlib import Path

from confluent_kafka import Producer

import daemon
from daemon import pidfile

from node import init_hosts
from service import init_services
from writer import init_output_workers, run_output_worker
from utils import load_sq_config

PID_FILE = '/tmp/suzieq.pid'


def validate_parquet_args(cfg, output_args):
    '''Validate user arguments for parquet output'''

    if not cfg.get('data-directory', None):
        output_dir = '/tmp/parquet-out/suzieq'
        logging.warning('No output directory for parquet specified, using'
                        '/tmp/suzieq/parquet-out')
    else:
        output_dir = cfg['data-directory']

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.isdir(output_dir):
        logging.error('Output directory {} is not a directory'.format(
            output_dir))
        print('Output directory {} is not a directory'.format(
            output_dir))
        sys.exit(1)

    logging.info('Parquet outputs will be under {}'.format(output_dir))
    output_args.update({'output_dir': output_dir})

    return


def validate_kafka_args(cfg, output_args):
    ''' Validate user arguments for kafka output'''

    if not cfg.get('kafka-servers', None):
        logging.warning('No kafka servers specified. Assuming localhost:9092')
        servers = 'localhost:9092'
    else:
        servers = cfg['kafka-servers']

    try:
        _ = Producer({'bootstrap.servers': servers})
    except Exception as e:
        logging.error('ERROR: Unable to connect to Kafka servers:{}, '
                      'error:{}'.format(servers, e))
        print('ERROR: Unable to connect to Kafka servers:{}, error:{}'
              .format(servers, e))
        sys.exit(1)

    output_args.update({'bootstrap.servers': servers})

    return


def _main(userargs, cfg):

    if not os.path.exists(cfg['service-directory']):
        logging.error('Service directory {} is not a directory'.format(
            userargs.output_dir))
        print('Service directory {} is not a directory'.format(
            userargs.output_dir))
        sys.exit(1)

    if not cfg.get('schema-directory', None):
        schema_dir = '{}/{}'.format(userargs.service_dir, 'schema')
    else:
        schema_dir = cfg['schema-directory']

    output_args = {}

    if 'parquet' in userargs.outputs:
        validate_parquet_args(cfg, output_args)

    if 'kafka' in userargs.outputs:
        validate_kafka_args(cfg, output_args)

    outputs = init_output_workers(userargs.outputs, output_args)

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    tasks = [init_hosts(userargs.hosts_file),
             init_services(cfg['service-directory'], schema_dir, queue)]

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
        tasks.append(run_output_worker(queue, outputs))
        loop.run_until_complete(asyncio.gather(*tasks))
        # loop.run_until_complete(svcs[2].run())
    except KeyboardInterrupt:
        logging.info('Received keyboard interrupt. Terminating')
        loop.close()
        sys.exit(0)


if __name__ == '__main__':

    homedir = str(Path.home())
    supported_outputs = ['parquet', 'kafka']

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--foreground', action='store_true',
                        help='Run in foreground, not as daemon')
    parser.add_argument('-H', '--hosts-file', type=str,
                        default='{}/{}'.format(homedir, 'suzieq-hosts.yml'),
                        help='FIle with URL of hosts to observe')
    parser.add_argument('-o', '--outputs', nargs='+', default=['parquet'],
                        choices=supported_outputs,
                        help='Output formats to write to: kafka, parquet. Use '
                        'this option multiple times for more than one output')
    parser.add_argument('-s', '--service-only', type=str,
                        help='Only run this comma separated list of services')

    userargs = parser.parse_args()
    cfg = load_sq_config()

    logger = logging.getLogger()
    logger.setLevel(cfg.get('logging-level', 'WARNING').upper())
    fh = logging.FileHandler(cfg.get('log-file', '/tmp/suzieq.log'))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s '
                                  '- %(message)s')
    logger.handlers = [fh]
    fh.setFormatter(formatter)

    if userargs.foreground:
        _main(userargs, cfg)
    else:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                pid = f.read().strip()
                if not pid.isdigit():
                    os.remove(PID_FILE)
                else:
                    try:
                        os.kill(int(pid), 0)
                    except OSError:
                        os.remove(PID_FILE)
                    else:
                        print('Another process instance of Suzieq exists with '
                              'pid {}'.format(pid))
        with daemon.DaemonContext(
                files_preserve=[fh.stream],
                pidfile=pidfile.TimeoutPIDLockFile(PID_FILE)):
            _main(userargs, cfg)
