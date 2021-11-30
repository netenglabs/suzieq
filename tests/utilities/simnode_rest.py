from aiohttp import web
import xmltodict
import argparse
import ssl
import logging


def get_filename_from_cmd(dictionary):

    keys = []

    def recursive_items(dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                keys.append(key)
                recursive_items(value)
            elif value:
                keys.append(key)
                keys.append(value)
            else:
                keys.append(key)

    recursive_items(dictionary)

    return "_".join(keys).replace("-", "_")


def run_server(nos="panos", version="default", hostname="default", port=443):

    nossim = f"tests/integration/nossim/{nos}/{version}/{hostname}"

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
            u = request.query.get("user", "")
            p = request.query.get("password", "")
            if u == username and p == password:
                return web.Response(text=auth_response)
            else:
                raise web.HTTPForbidden()

        # cmd queries
        elif req_type == "op" and req_auth_key == api_key:
            xml_cmd = request.query.get("cmd", "")

            if xml_cmd == "":
                raise web.HTTPBadRequest()

            cmd_dict = xmltodict.parse(xml_cmd)
            cmd = get_filename_from_cmd(cmd_dict)
            return web.FileResponse(f"{nossim}/{cmd}.xml")

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
        "-n", "--nos", type=str, default="panos",
        help="NOS name (default: iosxr)")
    parser.add_argument(
        "-v", "--nos-version", type=str,
        default="default", help="NOS version")
    parser.add_argument(
        "-H", "--hostname", type=str, default="default",
        help="Hostname of the device")
    parser.add_argument(
        "-p", "--listening-port", type=int, default=8443,
        help="Listening port of the ssh server (default: 8443)")
    args = parser.parse_args()

    run_server(
        nos=args.nos,
        version=args.nos_version,
        hostname=args.hostname,
        port=args.listening_port)
