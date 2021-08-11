#!/usr/bin/env python3

import sys
import argparse

from suzieq.restServer.query import rest_main


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str, help="alternate config file",
        default=None
    )
    parser.add_argument(
        "--no-https",
        help="Turn off HTTPS",
        default=False, action='store_true',
    )
    userargs = parser.parse_args()
    rest_main(userargs.config, userargs.no_https)
