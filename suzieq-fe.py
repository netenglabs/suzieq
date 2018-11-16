#!/usr/bin/python3

import sys
import os
import logging
import argparse
import yaml
from pathlib import Path
from confluent_kafka import Consumer, KafkaException

from time import sleep

import daemon
from daemon import pidfile

from livylib import get_or_create_livysession, exec_livycode

PID_FILE = '/tmp/suzieq-fe-init.pid'


def _main(cfg):
    '''The workhorse routine

    Parameters:
    -----------
    cfg: yaml object, YAML encoding of the config file
    '''

    session_url, response = get_or_create_livysession()
    if not session_url:
        logging.error('Unable to create a Livy session. Aborting')
        sys.exit(1)

    while True:
        # Sleep and send keepalives to keep the Spark session alive
        output = exec_livycode("""spark.conf.get('spark.app.name')""",
                               session_url)
        if output['status'] != 'ok':
            print(output)
        sleep(180)


def validate_sqcfg(cfg, fh):
    '''Validate Suzieq config file

    Parameters:
    -----------
    cfg: yaml object, YAML encoding of the config file
    fh:  file logger handle

    Returns:
    --------
    status: None if all is good or error string
    '''

    ddir = cfg.get('data-directory', None)
    if not ddir:
        return('No data directory for output files specified')

    sdir = cfg.get('service-directory', None)
    if not sdir:
        return('No service config directory specified')

    p = Path(sdir)
    if not p.is_dir():
        return('Service directory {} is not a directory'.format(sdir))

    scdir = cfg.get('service-directory', None)
    if not scdir:
        scdir = sdir + '/schema'

    p = Path(scdir)
    if not p.is_dir():
        return('Invalid schema directory specified')

    ksrv = cfg.get('kafka-servers', None)
    if ksrv:
        kc = Consumer({'bootstrap.servers': ksrv}, logger=fh)

        try:
            kc.list_topics(timeout=1)
        except KafkaException as e:
            return ('Kafka server error: {}'.format(str(e)))

        kc.close()

    return None


if __name__ == '__main__':

    parser = argparse.ArgumentParser('suzieq-fe')
    parser.add_argument('-f', '--foreground', action='store_true',
                        help='Run app in foreground, do not daemonize')
    parser.add_argument('-c', '--config-file', type=argparse.FileType('r'),
                        default='./config/suzieq-cfg.yml')

    userargs = parser.parse_args()

    cfg = yaml.load(userargs.config_file.read())

    logger = logging.getLogger()
    logger.setLevel(cfg.get('logging-level', 'WARNING'))
    fh = logging.FileHandler('/tmp/suzieq-fe.log')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s '
                                  '- %(message)s')
    logger.handlers = [fh]
    fh.setFormatter(formatter)

    status = validate_sqcfg(cfg, fh)
    if status:
        print('Invalid config, {}'.format(status))
        sys.exit(1)

    if userargs.foreground:
        _main(cfg)
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
                pidfile=pidfile.TimeoutPIDLockFile(PID_FILE)):
            _main(cfg)

