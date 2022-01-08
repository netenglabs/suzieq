'''
Serve up a fake REST server acting as device REST API
'''
import sys
import argparse
from pathlib import Path
import ssl
import logging

from aiohttp import web
import xmltodict


def get_filename_from_cmd(cmd_dict: dict) -> str:
    """Build filename from an xml command"""

    keys = []

    def recursive_items(cmd_dict: dict):
        for key, value in cmd_dict.items():
            if isinstance(value, dict):
                # do not use list entry for filename
                if key != "entry":
                    keys.append(key)
                recursive_items(value)
            elif value:
                # do not use property names for filename
                if not key.startswith("@"):
                    keys.append(key)
                keys.append(value)
            else:
                keys.append(key)

    recursive_items(cmd_dict)

    return "_".join(keys).replace("-", "_")


def run_server(port=443, input_dir: str = None):
    """Run sim rest server for the given nos, version and hostname"""

    api_key = "xxXYHqhFIAWAlWTulizbXtfVfvV5ETfNynHxAlV3ZEUTtrUNKZBDY3aKmCFC"

    auth_response = f"""<response status="success">
    <result>
        <key>{api_key}</key>
    </result>
</response>"""

    username = password = "vagrant"

    routes = web.RouteTableDef()

    @routes.get('/api/')
    async def panos_cmd(request):
        req_type = request.query.get("type", "")
        req_auth_key = request.headers.get("X-PAN-KEY", "") or \
            request.query.get("key", "")

        # authentication with user and pass to get api key
        if req_type == "keygen":
            user = request.query.get("user", "")
            passwd = request.query.get("password", "")
            if user == username and passwd == password:
                return web.Response(text=auth_response)

            raise web.HTTPForbidden()

        # cmd queries
        if req_type == "op" and req_auth_key == api_key:
            xml_cmd = request.query.get("cmd", "")

            if xml_cmd == "":
                raise web.HTTPBadRequest()

            cmd_dict = xmltodict.parse(xml_cmd)
            cmd = get_filename_from_cmd(cmd_dict)
            return web.FileResponse(f"{input_dir}/{cmd}.xml")

    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(
        'suzieq/config/etc/cert.pem', 'suzieq/config/etc/key.pem')

    app = web.Application()
    app.add_routes(routes)
    logging.basicConfig(level=logging.DEBUG)
    web.run_app(app, ssl_context=ssl_context, port=port)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--listening-port", type=int, default=10000,
        help="Listening port of the ssh server (default: 10000)")
    parser.add_argument(
        "-d", "--input-dir", type=str, default=None,
        help="Input dir to search for host files")
    args = parser.parse_args()

    if not Path(args.input_dir).exists():
        print(f'ERROR: Path {args.input_dir} does not exist, aborting')
        sys.exit(1)

    run_server(port=args.listening_port, input_dir=args.input_dir)
