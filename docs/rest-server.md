# Suzieq REST server

Suzieq ships with a REST server. It has the same set of commands, verbs and filters the the CLI has, with the exception of the verb "top". The output is always in JSON format at this time.

## Running the REST Server

The REST server is bundled with the Suzieq Docker image. It already has an API key and a self-signed SSL certificate to get you going without further ado. Real deployment of course involves changing these defaults with something specific to your enterprise. At this time it's only authentication
is via an API key and all access to the API is via SSL.

You must launch the Suzieq docker container as follows:```docker run -itd -p 8000:8000 --name suzieq ddutt/suzieq:0.6-prerc```
This assumes that you're using port 8000 to connect to the REST server. If you wish to use a different port for the REST server, say 7000, you can launch it as ```docker run -itd -p 7000:8000 --name suzieq ddutt/suzieq:0.6-prerc```.

You then connect to the container with ```docker attach suzieq```, and launch the server with ```sq-rest-server.py &```. You can then exit the container using the usual Docker container escape sequence CTRL-p CTRL-q to leave the docker container running. 

The server is now accessible via https://localhost:8000/docs (or whatever port you've mapped the server to on the host). You need to pass the API_KEY in the request to be able to access the server. A simple example using the default API key and certificate is to use curl as follows:```curl --insecure 'https://localhost:8000/api/v1/device/show?&access_token=496157e6e869ef7f3d6ecb24a6f6d847b224ee4f'```

The Suzieq docker container of course serves the data available under /suzieq/parquet inside the container. You can mount the parquet data you've already gathered via the -v option. So an example of mounting the parquet directory with data would be to launch the container as follows:```docker run -itd -p 8000:8000 -v/home/ddutt/work/suzieq/tests/data/multidc/parquet-out:/suzieq/parquet --name suzieq ddutt/suzieq:0.6-prerc```

The REST server has been implemented using the [fastapi](https://fastapi.tiangolo.com/) server.

## API Documentation

In keeping with the modern REST server design model, the rest server comes bundled with automatic documentation. You can point the browser at https://localhost:8000/docs for the classical Swagger-based documentation. This also allows you to try out the API from within the browser itself. You can also use the fastapi's alternative documentation at https://localhost:8000/redoc.

If you do decide to try out the API from within the browser, you need to authenticate it first using the Authorize button and adding the API Key.

## Creating Your Specific Key and SSL Certificate

If you wish to create your own self-signed certificate and API key, you can do so using the instructions in this section, in case you don't already know how to do so. 

### SSL 

### Create a self signed cert

The easiest way to go about getting a cert is a self signed cert. You can create this
via openssl.

The easiest way is:

``` bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```
The output of the command is two files, cert.pem and key.pem, created in the directory where you ran the command.

It's not likely that you'd want to use this in production. This certificate will expire in 365 days.

The REST server requires two files in ~/.suzieq, key.pem and cert.pem. Put these files in ~/.suzieq. Without those two files the REST server will not work.

### Setup API KEY

You do need a entry called API_KEY in your suzieq config file, which is usually in ~/.suzieq/suzieq.cfg.
It can be anything you want it to be. This will be the same key that you need to use from the client.

If you want it to be more random, this is a good way of creating a key:

``` bash
openssl rand -hex 20
```

### Changing the Location And Name of the Key/Cert Files

The default location for the key and certificate files needed for REST is ~/.suzieq, and the file names are key,pem and cert.pem. If you wish these to be different, you can specify the full path of each of the files (or any one) via the ```rest_keyfile``` and ```rest)_certfile``` variables in the suzieq config file, typically at ~/.suzieq/suzieq-cfg.yml. Here is an example of a config file with these two parameters defined:
```

data-directory: /suzieq/parquet
service-directory: /suzieq/config
schema-directory: /suzieq/config/schema
temp-directory: /tmp/
# kafka-servers: localhost:9093
logging-level: WARNING
period: 15
API_KEY: 496157e6e869ef7f3d6ecb24a6f6d847b224ee4f
rest_certfile: /suzieq/cert.pem
rest_keyfile: /suzieq/cert.pem
```
