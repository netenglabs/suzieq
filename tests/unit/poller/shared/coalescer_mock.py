#!/usr/bin/env python
"""
A simple application listening on a TCP port waiting for connections
"""
import argparse
import asyncio


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
        type=str, help="alternate config file"
    )

    server = await asyncio.start_server(wait_for_test, '127.0.0.1', 8303)

    print('Waiting for connection')

    await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
