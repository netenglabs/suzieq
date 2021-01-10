#!/usr/bin/env python3

import uvicorn
import argparse
import sys
import yaml
import os
from suzieq.utils import load_sq_config

from suzieq.restServer.query import app


def get_cert_files(cfg):
    ssl_certfile = cfg.get('rest_certfile',
                           os.getenv("HOME") + '/.suzieq/cert.pem')
    ssl_keyfile = cfg.get('rest_keyfile',
                          os.getenv("HOME") + '/.suzieq/key.pem')
    if not os.path.isfile(ssl_certfile) or not os.path.isfile(ssl_keyfile):
        print(
            "ERROR: Missing certificate files, {ssl_certfile}, {ssl_keyfile}")
        sys.exit(1)

    return ssl_certfile, ssl_keyfile


def get_log_file(cfg):
    tmp = cfg.get('temp-directory', '/tmp')
    return f"{tmp}/sq-rest-server.log"


def get_log_config():
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config['handlers']['access']['class'] = 'logging.handlers.RotatingFileHandler'
    log_config['handlers']['access']['maxBytes'] = 10000000
    log_config['handlers']['access']['backupCount'] = 2
    log_config['handlers']['default']['class'] = 'logging.handlers.RotatingFileHandler'
    log_config['handlers']['default']['maxBytes'] = 10_000_000
    log_config['handlers']['default']['backupCount'] = 2

    log_config['handlers']['access']['filename'] = get_log_file()
    del(log_config['handlers']['access']['stream'])
    log_config['handlers']['default']['filename'] = get_log_file()
    del(log_config['handlers']['default']['stream'])

    return log_config


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str, help="alternate config file",
        default=f'{os.getenv("HOME")}/.suzieq/'
    )
    userargs = parser.parse_args()
    cfg = load_sq_config(userargs.config)
    try:
        api_key = cfg['API_KEY']
    except KeyError:
        print('missing API_KEY in config file')
        exit(1)
    log_level = cfg.get('logging-level', 'INFO').lower()
    ssl_keyfile, ssl_certfile = get_cert_files(cfg)

    uvicorn.run(app, host="0.0.0.0", port=8000,
                log_level=log_level,
                log_config=get_log_config(),
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile)
