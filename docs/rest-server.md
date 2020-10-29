# Suzieq REST server

It is the same set of commands and verbs the the CLI has. At this time it's only authentication
is via an API key and all access to the API is via SSL.

It runs on port 8000.


The rest server takes a little bit to setup. It requires an SSL cert and an API Key

## SSL 

### Create a self signed cert

The easiest way to go about getting a cert is a self signed cert. You can create this
via openssl.

The easiest way is:

``` bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

It's not likely that you'd want to use this in production. This certificate will expire in 365 days.

### Setup Cert

The REST server requires two files in ~/.suzieq, key.pem and cert.pem. Put these files in ~/.suzieq. Without those two files the REST server will not work.

## Setup API KEY

You do need a entry called API_KEY in your suzieq config file, which is usually in ~/.suzieq/suzieq.cfg.
It can be anything you want it to be. This will be the same key that you need to use from the client.

If you want it to be more random, this is a good way of creating a key:

``` bash
openssl rand -hex 20
```

## Run the rest server

``` bash
python3 suzieq/server/restServer.py
```

It can take a config file as an arguement if you would like:

``` bash
python3 suzieq/server/restServer.py -c config.cfg
```

## API

The easiest way to understand the what is in the API is point a browser to https://myserver:8000/docs. This does not require an API_KEY but it does require SSL. You can see each of the commands and the arguments that
command can use.

## How to access the API

First off, if you are using a self signed cert, then clients will likely complain that it isn't secure.
This is okay, just a little tedius.

If you are using curl, you can use --insecure

Using the API_KEY is a little tricky. You can send the key either in the header or in a query.

In the header:

```bash
curl --insecure https://localhost:8000/api/v1/device/show -H "access_token: 68986cfafc9d5a2dc15b20e3e9f289eda2c79f40"
```

In the query:

```bash
curl --insecure https://localhost:8000/api/v1/device/show?access_token=68986cfafc9d5a2dc15b20e3e9f289eda2c79f40

```
