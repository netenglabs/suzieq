#!/usr/bin/env python
"""
A simple application listening on a TCP port waiting for connections
"""
import argparse
import asyncio
import os

from suzieq.shared.utils import ensure_single_instance, load_sq_config


async def wait_for_test(reader, writer):
    """New connections handler
    """
    print('Connection received')
    await reader.read(256)
    writer.close()
    await writer.wait_closed()


async def main():
    """Starts the server and listens for connections
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=f'{os.getenv("HOME")}/.suzieq/suzieq-cfg.yml',
        type=str, help="alternate config file"
    )
    userargs = parser.parse_args()

    server = await asyncio.start_server(wait_for_test, '127.0.0.1', 8303)

    print('Waiting for connection')

    # Create the file lock so that it is possible to check if there is a
    # coalescer running
    cfg = load_sq_config(config_file=userargs.config)
    coalesce_dir = cfg.get('coalescer', {})\
        .get('coalesce-directory',
             f'{cfg.get("data-directory")}/coalesced')
    ensure_single_instance(f'{coalesce_dir}/.sq-coalescer.pid',
                           False)

    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
