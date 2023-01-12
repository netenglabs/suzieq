# Rate Limiting AAA Server Requests

Many AAA servers (such as TACACS, Radius) cannot handle the rate at which SuzieQ can issue requests. This is especially true in larger installations, those with older AAA servers, or when command authorization is used in addition to authentication. The most common symptom of this problem is the authentication failed error message. To avoid user lockout, we stopped retrying on authentication failures. To fix this, we added three new parameters to the poller configuration. A consequence of throttling is of course that it takes longer to collect the data.

* **max-cmd-pipeline**: This is an integer value that ensures that no more than this number of requests are sent to a device in a second. Thus a value of 9 implies that we never have more than 9 outstanding commands or logins. If you use distributed pollers, you need to ensure that this number is a multiple of the number of pollers. Thus with a value of 9, you can use either 1 or 3 pollers. With 8, you can use 1, 2, or 4 pollers and so on. This is **specified in the suzieq-cfg.yml** file. The default is 0 i.e. no limits.

* **per-cmd-auth**: This is a boolean to specify whether need to throttle logins as well as commands sent to a device. This is required in installations where commands are authorized before execution. True means use it for commands as well as logins. This is specified in the devices section of the poller inventory file. The default is True.

* **retries-on-auth-fail**: Some older AAA servers fail even at low rates. In certain installations, a maximum of 3 authentication failures are tolerated before the user account is locked, and in some installations it can be anything more than a single failure. This parameter now enables us to support both types of installations. This is specified in the devices section of the poller inventory file. The default is 1, so the poller retries once after the first authentication failure.

Here's a sample suzieq-cfg.yml file with the max-cmd-pipeline parameter (see the poller section).
```
data-directory:  tests/data/parquet
coalescer:
   period: 1h
   archive-directory:
   logging-level: DEBUG
rest:
# Uncomment these lines if you're using your own files for the REST server
# The certificates listed below are provided purely to get started, In any
# secure deployment, these must be generated specifically for the site and
# these lines uncommented and containing the location of the site-specific file.
# rest_certfile: /suzieq/cert.pem
# rest_keyfile: /suzieq/key.pem
#
  API_KEY: 496157e6e869ef7f3d6ecb24a6f6d847b224ee4f
  logging-level: WARNING
  address: 127.0.0.1
  port: 8000
  # no-https: True
  log-stdout: True
  # rest-certfile: /secrets/cert.pem
  # rest-keyfile: /secrets/key.pem
  # logfile: /tmp/sq-rest-server.log
  # log-stdout: True

poller:
  connect-timeout: 60
  period: 60
  logsize: 10000000
  logging-level: WARNING
  log-stdout: True
  max-cmd-pipeline: 4

ux:
  engine: pandas

analyzer:
  timezone: America/Los_Angeles
```

Here's a sample inventory file with per-cmd-auth and retries-on-auth-fail set:
```
---
sources:
  - name: ans
    type: ansible
    path: /tmp/ansinv

devices:
  - name: default
    per-cmd-auth: False
	retries-on-auth-fail: 2
    ignore-known-hosts: true

auths:
  - name: default
    username: vagrant
    password: vagrant

namespaces:
  - name: demo
    source: ans
    device: default
```
