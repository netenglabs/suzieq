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

Here is an example of a complete inventory file:
```yaml
sources:
- name: netbox-instance-123
  token: af8717c89ec0ff420c19d89e6c20646ad55dd54e
  url: http://127.0.0.1:8000
  tag: suzieq-demo
  period: 3600

- name: dc-02-suzieq-native
  hosts:
  - url: ssh://vagrant@10.0.0.1:22 keyfile=/path/to/private_key
  - url: ssh://vagrant@10.0.0.2:22 devtype=eos keyfile=/path/to/private_key

- name: ansible-01
  type: ansible
  path: /path/to/ansible/list

devices:
- name: devices-with-jump-hosts
  transport: ssh
  jump-host: 127.0.0.1
  jump-host-key-file: /path/to/jump/key
  ignore-known-hosts: true
  port: 22
  devtype: eos

- name: devices-using-rest
  transport: rest

auths:
- name: credentials-from-file-0
  type: cred_file
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
  device: devices-00
  auth: credentials-from-file-0
```

## <a name='inventory-sources'></a>Sources

The device sources currently supported are:

- Suzieq native yaml (the same used with the old option `-D`)
- Ansible inventory, specifing a path to a file that has to be the output of ```ansible-inventory --list``` command
- Netbox

Each source must have a name so that it can be referred to in the `namespace` section.

Each source can contain a field called `copy`. This field is used to replicate and override the content of another source:
```yaml
- name: netbox-orig
  type: netbox
  token: your-api-token-here
  url: http://127.0.0.1:8000
  tag: suzieq-demo
  period: 3600

- name: netbox-copy     # This source will use the same set of parameters of 'netbox-orig'
  copy: netbox-orig     # and only overrides the 'tag' field.
  tag: suzieq-copy

```
### <a name='source-suzieq-native'></a>Suzieq native format

The Suzieq native format contains the IP address, the access method (SSH or REST), the IP address of the node, the user name, the type of OS if using REST and the access token such as a private key file. Here is an example of a native suzieq source type. For example (all possible combinations are shown for illustration):
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

If you're using Ansible to configure the devices, an alternate to the native Suzieq inventory format is to use an Ansible inventory format. The file to be used is the output of the ```ansible-inventory --list``` command.

Now you can set the path of the ansible inventory in the source:
```yaml
- name: ansible-01
  type: ansible
  path: /path/to/ansible/list
```

### <a name='source-netbox'></a>Netbox

Netbox is often used to store devices type, management address and other useful information to be used in network automation. Suzieq can pull device data from Netbox selecting them by tag (currently only one). To do so a token to access the netbox API is required as well as the netbox instance url.
The data are pulled from netbox periodically, the period can be set to any desired number in seconds (default is 3600).

Here is an example of the configuration of a netbox type source:
```yaml
- name: netbox-dc-01
  type: netbox
  token: your-api-token-here
  url: http://127.0.0.1:8000
  tag: suzieq-demo    # if not present, default is "suzieq"
  period: 3600
```

If you use a netbox source you need to define an authentication source since credentials al pulled from netbox.

## <a name='devices'></a>Devices

In this section you can specify some default settings to be applied to set of devices. You can bind this settings to a source in the `namespaces` section.

For example, if a set of devices is only reachable with a ssh jump, in `devices` you can define the jump host and the path to the jump-host key file. This way you define it once and possibly use it in multiple namespaces.

```yaml
- name: devices-with-jump-hosts
  transport: ssh
  jump-host: 10.0.0.1
  jump-host-key-file: /path/to/jump/key
  port: 22
```

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
## <a name='auths'></a>Auths

This section is optional in case Suzieq native and ansible source types. Here a set of default authentication sources can be defined. Currently a `cred_file` type and a static default type are defined. This way if credentials are not defined in the sources, default values can be applied.

Currently for both SSH and REST API, the only supported is username and password, therefore you will not be able to set api keys.

The simplest method is defining either username and password/private key.
```yaml
- name: suzieq-user
  username: suzieq
  password: plain:pass
```

where `password` can be specified in plaintext, as an environment variable or to be asked to the user:

- `plain:<password-in-plaintext>`
- `env:<ENV_VARIABLE>`
- `ask`

In case a private key is used to authenticate:
```yaml
- name: suzieq-user
  keyfile: path/to/private/key
  key-passphrase: ask
```

Where `key-passphrase` is the passphrase of the private key. As the `password` field, it can be set as plaintext, env variable or to be asked to the user.


The `cred_file` type is mandatory in case a Netbox source is used, in the `auths` section you can then define:

```yaml
- name: credentials-from-file-0
  type: cred_file
  path: /path/to/device/credentials.yaml
```

### <a name='cred_file'></a>Credential file

A `cred_file` is an external file where you store credentials for all the devices.
Each device credentials can be specified via its `hostname` or its `address`
(with Netbox, it's encouraged the usage of `hostname`).
The credential file should look like this:
```yaml
- namespace: testing
  - hostname: leaf01
    password: my-password
    username: vagrant
  - hostname: leaf02
    keyfile: /path/to/private/key
    username: vagrant
  - hostname: leaf03
    keyfile: /path/to/private/key
    username: vagrant
    key-passphrase: ask
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

In case you are using the Suzieq native or ansible source types, `auth` field is optional since the settings can be defined per-device in the source.

The `device` field is always optional since it only contains common configurations for all the devices in the namespace.

## <a name='running-poller'></a>Running the poller

Once you have generated the inventory file you can launch the poller inside the docker container using:

```
sq-poller -I inventory.yaml
```

The poller creates a log file called /tmp/sq-poller.log. You can look at the file for errors. The output is stored in the parquet directory specified under /suzieq/parquet and visible in the host, outside the container, via the path specified during docker run above.

## <a name='migrating-to-new-format'></a>Migrating Suzieq Native Inventory to new format

Starting with version 0.16.0, the Suzieq Native inventory format is no longer supported as is. We need to do some small changes to use it with the new version. Here is an example of creating a new `inventory.yml` from an old suzieq native inventory format.

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