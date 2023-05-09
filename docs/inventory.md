# <a name='inventory'></a>Gathering Data: Inventory File Format

The inventory file that the poller uses describes a set of sources used to gather the list of devices, credentials to authenticate in the devices, default settings and eventually puts all together defining namespaces. An extensive explanation of each secation is provided on this page.

!!! warning
    Starting with version 0.16.0 the old options `-D` and `-a`  and the old inventory format are no longer supported.
    See the section [Migrating to the new format](#migrating-to-new-format).

The new inventory is structured in 4 major pieces, explained in its own section:

- `sources`: a list of source to gather the list of devices
- `devices`: a list of default settings to be applied in case it is not possible to deduce them from the sources
- `auths`: a list of credential sources
- `namespaces`: where you put together all the above. A namespace is be defined by a `source`, an `auth` and a `device`

Here is an example of an inventory file with a bunch of different options, but non-exhaustive, for each section:

```yaml
sources:
- name: netbox-instance-123
  token: af8717c89ec0ff420c19d89e6c20646ad55dd54e
  url: http://127.0.0.1:8000
  tag:
  - suzieq-demo
  type: netbox
  period: 3600

- name: dc-02-suzieq-native
  hosts:
  - url: ssh://vagrant@10.0.0.1:22 keyfile=/path/to/private_key
  - url: https://vagrant@10.0.0.2:22 devtype=eos

- name: ansible-01
  type: ansible
  path: /path/to/ansible/list

devices:
- name: devices-without-jump-hosts
  ignore-known-hosts: true

- name: devices-with-jump-hosts
  transport: ssh
  jump-host: username@127.0.0.1
  jump-host-key-file: /path/to/jump/key
  ignore-known-hosts: true
  port: 22

- name: devices-using-rest
  transport: https
  devtype: eos

auths:
- name: credentials-from-file-0
  type: cred-file
  path: /path/to/device/credentials.yaml

- name: suzieq-user-01
  username: suzieq
  password: plain:pass

- name: suzieq-user-02
  username: suzieq
  password: env:PASSWORD_ENV_VAR

- name: suzieq-user-03
  username: suzieq
  password: ask

- name: suzieq-user-04
  key-passphrase: ask
  keyfile: path/to/key

namespaces:
- name: testing
  source: netbox-instance-123
  device: devices-with-jump-hosts
  auth: credentials-from-file-0
```

!!! warning
    Some observations on the YAML file above:

    - **This is just an example** that covers all the possible combinations, **not an real life inventory**
    - **Do not specify device type unless you're using REST**. SuzieQ automatically determines device type with SSH
    - Most environments require setting the `ignore-known-hosts` option in the device section
    - The auths section shows all the different authorization methods supported by SuzieQ
    - It is possible to [map different sources to the same namespace](#mapping-different-sources-to-the-same-namespace)

## <a name='sensitive-data'></a>Sensitive data

A sensitive data is an information that the user doesn't want to store in plain-text inside the inventory.
For this reason, SuzieQ inventory now supports three different options to store these kind of informations

- `plain:<password-in-plaintext>` or `<password-in-plaintext>`: the sensitive information is stored as is in the inventory
- `env:<ENV_VARIABLE>`: the sensitive information is stored in an environment variable
- `ask`: the user can write the sensitive information on the stdin

Currently this method is used to specify passwords, passphrases and tokens.

## <a name='inventory-sources'></a>Sources

The device sources currently supported are:

- Host list (the same used with the old option `-D` in SuzieQ 0.15.x or lower)
- Ansible inventory, specifing a path to a file that has to be the output of ```ansible-inventory --list``` command
- Netbox

Each source must have a name so that it can be referred to in the `namespace` section.

Whenever a source has many fields in common with another, you don't have to rewrite it. With the `copy: <source_name>` all the fields of `<source-name>` are automatically replicated, and it is possible to specify only the ones which changes:

```yaml
- name: netbox-orig
  type: netbox
  token: your-api-token-here
  url: http://127.0.0.1:8000
  tag:
  - suzieq-demo
  period: 3600

- name: netbox-copy     # This source will use the same set of parameters of 'netbox-orig'
  copy: netbox-orig     # and only overrides the 'tag' field.
  tag:
  - suzieq-copy

```

### <a name='source-host-list'></a>Host list

The host list contains the IP address, the access method (SSH or REST), the IP address of the node, the user name, the type of OS if using REST and the access token such as a private key file. Here is an example of a native suzieq source type. For example (all possible combinations are shown for illustration):

```yaml
- name: dc-01-native
  type: native # optional, if type is not present this is the default value
  hosts:
    - url: https://vagrant@192.168.123.252 devtype=eos
    - url: ssh://vagrant@192.168.123.232  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/internet/libvirt/private_key
    - url: https://vagrant@192.168.123.164 devtype=eos
    - url: ssh://192.168.123.70 username=admin password=admin
    - url: ssh://vagrant@192.168.123.230  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server101/libvirt/private_key
    - url: ssh://vagrant@192.168.123.54:2023  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server104/libvirt/private_key
    - url: https://vagrant@192.168.123.123 password=vagrant
```

There's a template in the docs directory called `hosts-template.yml`. You can copy that file as the template and fill out the values for namespace and url (remember to delete the empty URLs and to not use TABS, some editors add them automatically if the filename extension isn't right). The URL is the standard URL format: `<transport>://[username:password]@<hostname or IP>:<port>`. For example, `ssh://dinesh:dinesh@myvx` or `ssh://dinesh:dinesh@172.1.1.23`.

### <a name='source-ansible'></a>Ansible

If you are using Ansible to configure the devices, it is possible to set the output of the ```ansible-inventory --list``` command as an input source.
Once you created a json file containing the result of the command, with:

```shell
ansible-inventory --list > ansible.json
```

Now you can set the path of the ansible inventory in the source:

```yaml
- name: ansible-01
  type: ansible
  path: /path/to/ansible.json
```

Since Ansible devices cannot really be split up, the device and auth sections apply to **all** the devices in the Ansible inventory file. This is a limitaion of the Ansible source input. We always assume ssh as the transport unless otherwise specified in the device section of the SuzieQ inventory file. 
!!! info
    From 0.21.0, with Ansible inventories, the device type and transport are taken from the specification in the device section of the suzieq inventory file. You must specify the transport as rest if you want to use rest as the transport for EOS devices. By default, we assume ssh as the transport. For PANOS also, you must specify the device type and transport. Before version 0.21.0, Ansible inventory assumed REST as the transport for EOS, even if the user specified the transport as SSH in the device section.

### <a name='source-netbox'></a>Netbox

[Netbox](https://netbox.readthedocs.io/en/stable/) is often used to store devices type, management address and other useful information to be used in network automation.
SuzieQ can pull device data from Netbox selecting them by one or more tags.
To grant access to netbox, a token and an url must be provided.
The token is considered a [sensitive data](#sensitive-data), so it can be specified via an environment variable using the format `env:ENV_TOKEN`.

Since Netbox is a _dynamic source_, the data are periodically pulled, the period can be set to any desired number in seconds (default is 3600).

!!!Info
    Each netbox source contains a parameter called `ssl-verify`.
    This parameter is used to specify whether perform ssl certificate verify or not. By default `ssl-verify` is set to _true_ if the url contains an https host.
    If the user manually sets `ssl-verify: true` with an http netbox server, an error will be notified.

Here is an example of the configuration of a netbox type source:

```yaml
- name: netbox-dc-01
  type: netbox
  token: your-api-token-here
  url: https://127.0.0.1:8000
  tag:                # if not present, default is "suzieq"
  - suzieq-demo
  period: 3600        # How frequently Netbox should be polled
  ssl-verify: false   # Netbox certificate validation will be skipped
```

#### Selecting devices from Netbox

Starting from 0.19, it's possible to specify more than one tag to be matched, defining a list of one or more rules.
A single rule can contain a set of tags divided by the `,` separator, which should **ALL** be matched.
A device is polled by SuzieQ if it matches at least one of the defined rules.

```yaml
- name: netbox-multi-tag
  type: netbox
  token: your-api-token-here
  url: https://127.0.0.1:8000
  tag:
  - alpha
  - bravo, charlie
```

For example, the source above tells SuzieQ to select from Netbox all the devices having the `alpha` OR `bravo & charlie` tags.

!!!Warning
    SuzieQ versions older than 0.19 supported one single tag.
    The old syntax, following the pattern `tag: netbox-tag`, is deprecated and it might be removed in the future releases.

#### Map Netbox sitenames to namespaces

Netbox type source is capable to assign each device to a namespace which corresponds to the device's sitename.
To obtain this behaviour, we need to declare a `namespace` object with `name: netbox-sitename`.

Here is an example:

```yaml
sources:
- name: netbox-dc-01
  type: netbox
  token: your-api-token-here
  url: http://127.0.0.1:8000
  tag:
  - tag1
  - tag2, tag3

- name: netbox-dc-02
  type: netbox
  token: your-api-token-here
  url: http://127.0.0.1:9000
  tag:
  - suzieq

auths:
- name: auth-st
  username: user
  password: my-password

namespaces:
- name: netbox-sitename # devices namespaces equal to their site names
  source: netbox-dc-01
  auth: auth-st

- name: namespace01     # devices namespaces equal to 'namespace01'
  source: netbox-dc-02
  auth: auth-st

```

!!! warning
    Credentials are not pulled from netbox, you will need to define an authentication source under the [auths](#auths) get the nodes' credentials.

## <a name='devices'></a>Devices

In this section you can specify some default settings to be applied to set of devices. You can bind this settings to a source in the `namespaces` section.

For example, if a set of devices is only reachable with a ssh jump, in `devices` you can define the jump host and the path to the jump-host key file. This way you define it once and possibly use it in multiple namespaces.

```yaml
- name: devices-with-jump-hosts
  transport: ssh
  jump-host: username@10.0.0.1
  jump-host-key-file: /path/to/jump/key
  port: 22
```

The supported transport methods are `https` and `ssh`.

In case you want to ignore the check of the device's key against the `known_hosts` file you can set:

```yaml
- name: devices-ignoring-known-hosts
  ignore-known-hosts: true
```

Moreover if all the devices inside a namespace run the same NOS, it is possible to specify it via the `devtype` option:

```yaml
- name: eos-devices
  devtype: eos
```

!!! information
    The fields specified in the `device` section are treated as default values, which are provided if the node does not have one. Fields such as `devtype` or `transport` could be already provided by the source, in this case device will not override them.

### Limiting commands and authentication attempts

The device section provides some instruments to reduce the amount of commands and authentication attempts that the poller issues.

- **retries-on-auth-fail**: tells the poller how many times it can retry the authentication after the first failure. By **default** the poller retries **only once** after the first failure.
- **per-cmd-auth**: when all the commands are authorized before execution, someone might want to limit the number of issued commands. Setting this value to `True` enables throttling of the commands as well as logins. The number of logins (and issued commands) per second is specified in `max-cmd-pipeline` in the poller section of the [configuration file](./config_file.md), if this number is 0 or unspecified, then the value of `per-cmd-auth` has no effect. Default is True.

Additional information can be found in [Rate Limiting AAA Server Requests](./rate-limiting-AAA.md).

## <a name='auths'></a>Auths

This section is optional in case SuzieQ native and ansible source types. Here a set of default authentication sources can be defined. Currently a `cred-file` type and a static default type are defined. This way if credentials are not defined in the sources, default values can be applied.

Currently for both SSH and REST API, the only supported is username and password, therefore you will not be able to set api keys.

The simplest method is defining either username and password/private key.

```yaml
- name: suzieq-user
  username: suzieq
  password: plain:pass
```

In case a private key is used to authenticate:

```yaml
- name: suzieq-user
  keyfile: path/to/private/key
  key-passphrase: ask
```

Where `key-passphrase` is the passphrase of the private key.

Both `passoword` and `key-passphrase` are considered [sensitive data](#sensitive-data).
For this reason they can be set as plaintext, env variable or asked to the user via stdin.

### <a name='cred-file'></a>Credential file

All the fields specified directly inside an authentication source (i.e. `username`, `password`, `keyfile`, etc.) are used as default if the values are not provided. When the source do not provide the credentials, such as Netbox, we might want to specify different credentials for each device. This can be easily achieved via a `cred-file`, referenced in the `auths` section like in the following example:

```yaml
- name: credentials-from-file-0
  type: cred-file
  path: /path/to/device/credentials.yaml
```

A `cred-file` is an external file where you store credentials for all the devices.
Each device credentials can be specified via its `hostname` or its `address`
(with Netbox, it's encouraged the usage of `hostname`).
The credential file should look like this:

```yaml
- namespace: testing
  devices:
  - hostname: leaf01
    password: my-password
    username: vagrant
  - hostname: leaf02
    keyfile: /path/to/private/key
    username: vagrant
  - hostname: leaf03
    keyfile: /path/to/private/key
    username: vagrant
    key-passphrase: my-passphrase
  - address: 10.0.0.1
    username: vagrant
    password: my-password
```

## <a name='namespaces'></a>Namespaces

In the `namespaces` section sources, auths and devices can be put together to define namespaces.
For example the following namespace will be defined by the source named `netbox-1`, the auths named `dc-01-credentials`, and the device named `ssh-jump-devs`:

```yaml
namespaces:
- name: example
  source: netbox-1
  device: ssh-jump-devs
  auth: dc-01-credentials
```

In case you are using the SuzieQ native or ansible source types, `auth` field is optional since the settings can be defined per-device in the source.

The `device` field is always optional since it only contains common configurations for all the devices in the namespace.

### Mapping different sources to the same namespace

In some cases you might need to get the the devices from different sources but all of them should stay in the same namespace. This can be easily achieved by repeating the namespace for each of the desired sources. This also allows to have different device or auth sections for each of the sources:

```yaml
sources:
  - name: single
    hosts:
      - url: ssh://vagrant@localhost:10000 password=vagrant

  - name: slowpoke
    hosts:
      - url: ssh://vagrant@10.255.3.10 password=vagrant

  - name: mixed
    hosts:
      - url: https://vagrant@10.0.0.2:22 devtype=eos
      - url: ssh://vagrant@192.13.1.1 password=vagrant

devices:
  - name: default
    ignore-known-hosts: true

  - name: slow
    ignore-known-hosts: true
    slow_host: true

  - name: default-rest
    transport: https
    devtype: eos

namespaces:
  - name: testing
    source: single
    device: default

  - name: testing
    source: slowpoke
    device: slow

  - name: testing
    source: mixed
    device: default
```

## <a name='running-poller'></a>Running the poller

Once you have generated the inventory file you can launch the poller with the following command:

```shell
sq-poller -I inventory.yaml
```

## <a name='migrating-to-new-format'></a>Migrating SuzieQ Native Inventory to new format

Starting with version 0.16.0, the SuzieQ Native inventory format is no longer supported as is. We need to do some small changes to use it with the new version. Here is an example of creating a new `inventory.yml` from an old suzieq native inventory format.

Suppose we have this inventory valid for version 0.15.x:

```yaml
- namespace: eos
  hosts:
    - url: https://vagrant@192.168.123.252 devtype=eos
    - url: ssh://vagrant@192.168.123.232  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/internet/libvirt/private_key
    - url: https://vagrant@192.168.123.164 devtype=eos
    - url: ssh://192.168.123.70 username=admin password=admin
    - url: ssh://vagrant@192.168.123.230  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server101/libvirt/private_key
    - url: ssh://vagrant@192.168.123.54:2023  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server104/libvirt/private_key
    - url: https://vagrant@192.168.123.123 password=vagrant
```

The new inventory format consists of four sections (sources, auths, devices, namespaces) which are described above. We need to add the devices specified in the old inventory format in a new source inside the `sources` section and link it to a namespace.

Here is how the new format will look like:

!!! important
    Sections [auths](#auths) and [devices](#devices) are optional. See the full documentation to know how to use them.

```yaml
sources:
- name: eos-source # namespace is defined below, this is only a name to be used as reference
  hosts:
    - url: https://vagrant@192.168.123.252 devtype=eos
    - url: ssh://vagrant@192.168.123.232  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/internet/libvirt/private_key
    - url: https://vagrant@192.168.123.164 devtype=eos
    - url: ssh://192.168.123.70 username=admin password=admin
    - url: ssh://vagrant@192.168.123.230  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server101/libvirt/private_key
    - url: ssh://vagrant@192.168.123.54:2023  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server104/libvirt/private_key
    - url: https://vagrant@192.168.123.123 password=vagrant

namespaces:
- name: eos
  source: eos-source
```
