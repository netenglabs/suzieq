#!/usr/bin/env python3

import uvicorn
import argparse
import sys
import yaml
import os
from suzieq.utils import load_sq_config, get_sq_install_dir

from suzieq.restServer.query import app_init


def get_cert_files(cfg):
    sqdir = get_sq_install_dir()
    ssl_certfile = cfg.get('rest', {}) \
                      .get('rest_certfile', f'{sqdir}/config/etc/cert.pem')

    ssl_keyfile = cfg.get('rest', {}) \
                     .get('rest_keyfile', f'{sqdir}/config/etc/key.pem')

    if not os.path.isfile(ssl_certfile):
        print(f"ERROR: Missing certificate file: {ssl_certfile}")
        sys.exit(1)

    if not os.path.isfile(ssl_keyfile):
        print(f"ERROR: Missing certificate file: {ssl_keyfile}")
        sys.exit(1)

    return ssl_keyfile,  ssl_certfile


def get_log_file(cfg):
    tempdir = cfg.get('temp-directory', '/tmp')
    if not os.path.exists(tempdir):
        os.makedirs(tempdir, exist_ok=True)

    return f"{tempdir}/sq-rest-server.log"


def get_log_config(cfg):
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config['handlers']['access']['class'] = 'logging.handlers.RotatingFileHandler'
    log_config['handlers']['access']['maxBytes'] = 10000000
    log_config['handlers']['access']['backupCount'] = 2
    log_config['handlers']['default']['class'] = 'logging.handlers.RotatingFileHandler'
    log_config['handlers']['default']['maxBytes'] = 10_000_000
    log_config['handlers']['default']['backupCount'] = 2

    log_config['handlers']['access']['filename'] = get_log_file(cfg)
    del(log_config['handlers']['access']['stream'])
    log_config['handlers']['default']['filename'] = get_log_file(cfg)
    del(log_config['handlers']['default']['stream'])

    return log_config


def rest_main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str, help="alternate config file",
        default=f'{os.getenv("HOME")}/.suzieq/suzieq-cfg.yml'
    )
    userargs = parser.parse_args()
    app = app_init(userargs.config)
    cfg = load_sq_config(config_file=userargs.config)
    try:
        api_key = cfg['rest']['API_KEY']
    except KeyError:
        print('missing API_KEY in config file')
        exit(1)

    log_level = cfg.get('rest', {}).get('logging-level', 'INFO').lower()
    ssl_keyfile, ssl_certfile = get_cert_files(cfg)

    srvr_addr = cfg.get('rest', {}).get('address', '127.0.0.1')
    srvr_port = cfg.get('rest', {}).get('port', 8000)

    uvicorn.run(app, host=srvr_addr, port=srvr_port,
                log_level=log_level,
                log_config=get_log_config(cfg),
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile)


if __name__ == "__main__":
    rest_main()
