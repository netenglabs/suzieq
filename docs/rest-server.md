# Suzieq REST server

Suzieq ships with a REST server. It has the same set of commands, verbs and filters the the CLI has, with the exception of the verb "top". The output is always in JSON format at this time.

## Running the REST Server

The REST server is bundled with the Suzieq Docker image. It already has an API key and a self-signed SSL certificate to get you going without further ado. Real deployment of course involves changing these defaults with something specific to your enterprise. At this time it's only authentication
is via an API key and all access to the API is via SSL.

You can launch the Suzieq docker container as follows:

```shell
docker run -it -p 8000:8000 --name suzieq netenglabs/suzieq:latest
```

!!! info
    This assumes that you're using port 8000 to connect to the REST server. If you wish to use a different port for the REST server, say 7000, you can launch it as ```docker run -it -p 7000:8000 --name suzieq netenglabs/suzieq:latest```

You then launch the server with ```sq-rest-server.py &```. You can then exit the container using the usual Docker container escape sequence CTRL-p CTRL-q to leave the docker container running.

The server is now accessible via [https://localhost:8000/api/docs](https://localhost:8000/api/docs) (or whatever port you've mapped the server to on the host). You need to pass the API_KEY in the request to be able to access the server. A simple example using the default API key and certificate is to use curl as follows:

```shell
curl --insecure 'https://localhost:8000/api/v2/device/show?access_token=496157e6e869ef7f3d6ecb24a6f6d847b224ee4f'
```

The Suzieq docker container of course serves the data available under `/home/suzieq/parquet` inside the container. You can mount the parquet data you've already gathered via the `-v` option. So an example of mounting the parquet directory with data would be to launch the container as follows:

```shell
docker run -it -p 8000:8000 -v /path/to/you/suzieq-data:/home/suzieq/parquet --name suzieq netenglabs/suzieq:latest
```

The REST server has been implemented using the [fastapi](https://fastapi.tiangolo.com/) server.

## API Documentation

In keeping with the modern REST server design model, the rest server comes bundled with automatic documentation. You can point the browser at [https://localhost:8000/api/docs](https://localhost:8000/api/docs) for the classical Swagger-based documentation. This also allows you to try out the API from within the browser itself. You can also use the fastapi's alternative documentation at [https://localhost:8000/api/redoc](https://localhost:8000/api/redoc). The openapi.json URL is [https://localhost:8000/api/openapi.json](https://localhost:8000/api/openapi.json). We changed the default URLs for the Swagger and Redoc API as well as OpenAPI to make it easier for reverse proxies such as Caddy.

!!! warning
    If you do decide to try out the API from within the browser, you need to authenticate it first using the Authorize button and adding the API Key.

### Setup the API KEY

You do need a entry called API_KEY in your suzieq config file, which is usually in ~/.suzieq/suzieq.cfg.
It can be anything you want it to be. This will be the same key that you need to use from the client.

If you want it to be more random, this is a good way of creating a key:

```shell
openssl rand -hex 20
```

## Configure SSL Key and Certificate

It is possible to secure connections to the REST server via SSL. You can specify the full path of your SSL key and certificate via the ```rest_keyfile``` and ```rest_certfile``` variables under the `rest` section of the suzieq config file, typically at `~/.suzieq/suzieq-cfg.yml`. Here is an example of a config file with these two parameters defined:

```yaml
rest:
    rest_certfile: /home/suzieq/cert.pem
    rest_keyfile: /home/suzieq/cert.pem
```

For more details about the configuration file, check the [configuration](config_file.md) file documentation.

!!! warning
    By default the rest server has HTTPS enabled with some default self-signed certificates, to let users play with SuzieQ without further ado. Please, always provide your own certificates.

### Create a self signed cert

The easiest way to go about getting a cert is a self signed cert. You can create this via openssl:

```shell
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

The command above generates two files: `cert.pem` and `key.pem`, created in the directory where you ran the command. The certificate will expire after 365 days.

!!! danger
    Self-signed certificates should never be used in production.


### Disable HTTP on the rest server

In same cases you might want to disable HTTPS from the REST server, for example when TLS connections are terminated by a reverse proxy.
HTTPS can be disabled by setting to `true` the `no-https` field under the `rest` section of the config file, as in the following example:

```yaml
rest:
    no-https: true
```
