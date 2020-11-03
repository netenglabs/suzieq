#!/usr/bin/env python3

import uvicorn
import argparse
import sys
import yaml
import os

from suzieq.restServer.query import app, get_configured_api_key 

def check_config_file(cfgfile):
    if cfgfile:
        with open(cfgfile, "r") as f:
            cfg = yaml.safe_load(f.read())

        validate_sq_config(cfg, sys.stderr)


def check_for_cert_files():
    if not os.path.isfile(os.getenv("HOME") + '/.suzieq/key.pem') or not \
            os.path.isfile(os.getenv("HOME") + '/.suzieq/cert.pem'):
        logger.error(f"ERROR: Missing cert files in ~/.suzieq")
        print(f"ERROR: Missing cert files in ~/.suzieq")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str, help="alternate config file"
    )
    userargs = parser.parse_args()
    check_config_file(userargs.config)
    app.cfg_file = userargs.config
    get_configured_api_key()
    check_for_cert_files()
    uvicorn.run(app, host="0.0.0.0", port=8000,
                log_level='info', ssl_keyfile=os.getenv("HOME") + '/.suzieq/key.pem',
                ssl_certfile=os.getenv("HOME") + '/.suzieq/cert.pem')
