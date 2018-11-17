#!/usr/bin/python3

import sys
import os
import logging
import argparse
from time import sleep
import daemon
from daemon import pidfile

from livylib import get_or_create_livysession, exec_livycode
from utils import load_sq_config

PID_FILE = '/tmp/suzieq-fe-init.pid'


def _main(logger):
    '''The workhorse routine

    Parameters:
    -----------
    cfg: yaml object, YAML encoding of the config file
    '''

    session_url, _ = get_or_create_livysession()
    if not session_url:
        logger.error('Unable to create a Livy session. Aborting')
        sys.exit(1)

    while True:
        # Sleep and send keepalives to keep the Spark session alive
        output = exec_livycode("""spark.conf.get('spark.app.name')""",
                               session_url)
        if output['status'] != 'ok':
            print(output)
        sleep(180)

if __name__ == '__main__':

    parser = argparse.ArgumentParser('suzieq-fe')
    parser.add_argument('-f', '--foreground', action='store_true',
                        help='Run app in foreground, do not daemonize')

    userargs = parser.parse_args()

    cfg = load_sq_config()
    if not cfg:
        print('Invalid or unknown config')
        sys.exit(1)

    logger = logging.getLogger()
    logger.setLevel(cfg.get('logging-level', 'WARNING'))
    fh = logging.FileHandler('/tmp/suzieq-fe.log')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s '
                                  '- %(message)s')
    logger.handlers = [fh]
    fh.setFormatter(formatter)

    if userargs.foreground:
        _main(logger)
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
            _main(logger)