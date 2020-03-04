# Purge old counter files to keep disk utilization low

import os
import sys
from pathlib import Path
import fnmatch
import time
from daemon import pidfile
import daemon
import logging
import argparse

PID_FILE = '/tmp/suzieq-clean.pid'


def cleandir(userargs):

    while True:
        hostdirs = Path(userargs.output_dir).rglob('hostname=*')
        older_than_secs = time.time() - 3600*userargs.older_than
        for dir in hostdirs:
            flst = fnmatch.filter(os.listdir(dir), '*.parquet')
            if len(flst) > 240:
                # Only counters have files with .parquet files under hostname
                # partition. 240 because that's roughly an hour worth of data
                # when counters are collected every 15s. Why an hour? No
                # reason.

                for file in flst:
                    fpath = dir.joinpath(file)
                    if fpath.stat().st_ctime < older_than_secs:
                        fpath.unlink()

        # Wake up every hour
        time.sleep(3600)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--foreground', action='store_true',
                        help='Run in foreground, not as daemon')
    parser.add_argument('-O', '--output-dir', type=str, required=True,
                        help='Top level parqeut directory to monitor')
    parser.add_argument('-o', '--older-than', type=int, required=True,
                        help='Number of hours to wait before deleting a file')
    parser.add_argument('-l', '--log', type=str, default='WARNING',
                        choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'],
                        help='Logging message level, default is WARNING')

    userargs = parser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(userargs.log.upper())
    fh = logging.FileHandler('/tmp/suzieq-clean.log')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s '
                                  '- %(message)s')
    logger.handlers = [fh]
    fh.setFormatter(formatter)

    if (not os.path.exists(userargs.output_dir) or
            not os.path.isdir(userargs.output_dir)):
        print('ERROR: {} is not a direcory'.format(userargs.output_dir))
        sys.exit(1)

    if userargs.foreground:
        cleandir(userargs)
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
            cleandir(userargs)
