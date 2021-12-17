# Gathering Data: Poller

To gather data from your network, you need to run the poller. We support gathering data from Arista EOS, Cisco's IOS, IOS-XE, and IOS-XR platforms, Cisco's NXOS (N7K with versions 8.4.4 or higher, and N9K with versions 9.3.1 or higher), Cumulus Linux, Juniper's Junos(QFX, EX, MX and SRX platforms), and SoNIC devices, besides Linux servers

To start, launch the docker container, **netenglabs/suzieq:latest** and attach to it via the following steps:

```
  docker run -itd -v /home/${USER}/parquet-out:/suzieq/parquet -v /home/${USER}/<inventory-file>:/suzieq/inventory --name sq-poller netenglabs/suzieq:latest
  docker attach sq-poller
```

In the docker run command above, the two `-v` options provide host file/directory access to (i) store the parquet output files (the first `-v` option), and (ii) the inventory file (the second `-v` option). We describe the inventory file below. The inventory file is the list of devices and their IP address that you wish to gather data from. 

You then launch the poller via the command line:

```bash
  sq-poller -I inventory.yaml
```

To monitor the status of the poller, you can look at /tmp/sq-poller.log file.

The inventory file that the poller uses describes a set of sources used to gather the list of devices, credentials to authenticate in the devices, default settings and eventually puts all together defining namespaces. An extensive explanation of each secation is provided on this page. The old options `-D` and `-a` are no longer supported.

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
  tag: suzieq-demo # if not present, default is "suzieq"
  period: 3600

- name: dc-02-suzieq-native
  hosts:
  - url: ssh://vagrant@10.0.0.1:22 keyfile=/path/to/private_key
  - url: ssh://vagrant@10.0.0.2:22 devtype=eos keyfile=/path/to/private_key

- name: ansible-01
  type: ansible
  file_path: /path/to/ansible/list

devices: # default settings
- name: devices-with-jump-hosts
  transport: ssh
  jump-host: 127.0.0.1
  jump-host-key-file: /path/to/jump/key
  # ignore-known-hosts: true

- name: devices-using-rest
  transport: rest

auths:
- name: credentials-from-file-0
  type: cred_file
  file_path: /path/to/device/credentials.yaml

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
- namespace: testing
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
### <a name='source-suzieq-native'></a>Suzieq native format

The Suzieq native format contains the IP address, the access method (SSH or REST), the IP address of the node, the user name, the type of OS if using REST and the access token such as a private key file. Here is an example of a native suzieq source type. For example (all possible combinations are shown for illustration):
```yaml
- name: dc-01-native
  type: file # optional, if type is not present this is the default value
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

## <a name='device'></a>Devices

In this section you can specify some default settings to be applied to set of devices. You can bind this settings to a source in the `namespaces` section.

For example, if a set of devices is only reachable with a ssh jump, in `devices` you can define the jump host and the path to the jump-host key file. This way you define it once and possibly use it in multiple namespaces.

```yaml
- name: devices-with-jump-hosts
  transport: ssh
  jump-host: 10.0.0.1
  jump-host-key-file: /path/to/jump/key
```

In case you want to ignore the check of the device's key against the `known_hosts` file you can set:

```yaml
- name: devices-ignoring-known-hosts
  ignore-known-hosts: true
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

A `cred_file` is an external file where you store your credentials. It should look like this:
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
```

## <a name='namespaces'></a>Namespaces

In the `namespaces` section sources, auths and devices can be put together to define namespaces.
For example the following namespace will be defined by the source named `netbox-1`, the auths named `dc-01-credentials`, and the device named `ssh-jump-devs`:
```yaml
namespaces:
- namespace: example
  source: netbox-1
  device: ssh-jump-devs
  auth: dc-01-credentials
```

In case you are using the Suzieq native or ansible source types, auths and devices are optional since the settings can be defined per-device in the source.

## <a name='running-poller'></a>Running the poller

Once you have generated the inventory file you can launch the poller inside the docker container using:

```
sq-poller -I inventory.yaml
```

The poller creates a log file called /tmp/sq-poller.log. You can look at the file for errors. The output is stored in the parquet directory specified under /suzieq/parquet and visible in the host, outside the container, via the path specified during docker run above. 

## <a name='gathering-data'></a>Gathering Data
Two important concepts in the poller are Nodes and Services. Nodes are devices of some kind;
they are the object being monitored. Services are the data that is collected and consumed by Suzieq. 
Service definitions describe how to get output from devices and then how to turn that into useful data.

Currently Suzieq supports polling [Arista](https://www.arista.com/en/),
[Cisco's IOS](https://www.cisco.com/c/en/us/products/ios-nx-os-software/ios-technologies/index.html) including IOS Classic, IOS-XE and IOS-XR,
[Cisco's NXOS](https://www.cisco.com/c/en/us/products/switches/data-center-switches/index.html),
[Cumulus Linux](https://cumulusnetworks.com/),
[Juniper](https://www.juniper.net),
and [SONIC](https://azure.github.io/SONiC/) devices, as well as native Linux devices such as servers. Suzieq can easily support other device types, and we have third-party contributors working on other NOSes. Please let us know if you're interested in Suzieq supporting other NOSes.

Suzieq started out with least common denominator SSH and REST access to devices.
It doesn't care much about transport, we will use whatever gets the best data.
Suzieq does have support for agents, such as Kafka and SNMP, to push data and we've done some experiments with them, but don't
have production versions of that code. 

## Debugging poller issues
There are two places to look if you want to know what the poller is up to. The first is the poller
log file in */tmp/sq-poller.log*. The second is in Suzieq in the sq-poller table. We keep data about how
polling is going in that table. If you do `suzieq-cli sqpoller show --status=fail` you should see any failures.

```
jpietsch> sqpoller show status=fail namespace=dual-evpn
     namespace   hostname  service  status gatherTime totalTime svcQsize wrQsize nodeQsize  pollExcdPeriodCount               timestamp
     18   dual-evpn     edge01     mlag     404         []        []       []      []        []                    0 2020-06-17 05:14:40.285
     257  dual-evpn  server101      bgp       1         []        []       []      []        []                    0 2020-06-17 05:14:40.980
     260  dual-evpn  server101  evpnVni       1         []        []       []      []        []                    0 2020-06-17 05:14:38.145
     271  dual-evpn  server101     mlag     404         []        []       []      []        []                    0 2020-06-17 05:14:38.792
     272  dual-evpn  server101   ospfIf       1         []        []       []      []        []                    0 2020-06-17 05:14:38.138
     273  dual-evpn  server101  ospfNbr       1         []        []       []      []        []                    0 2020-06-17 05:14:40.593
     284  dual-evpn  server102      bgp       1         []        []       []      []        []                    0 2020-06-17 05:14:41.712
     287  dual-evpn  server102  evpnVni       1         []        []       []      []        []                    0 2020-06-17 05:14:38.831
     298  dual-evpn  server102     mlag     404         []        []       []      []        []                    0 2020-06-17 05:14:39.121
     299  dual-evpn  server102   ospfIf       1         []        []       []      []        []                    0 2020-06-17 05:14:38.831
     300  dual-evpn  server102  ospfNbr       1         []        []       []      []        []                    0 2020-06-17 05:14:41.036
     311  dual-evpn  server103      bgp       1         []        []       []      []        []                    0 2020-06-17 05:14:40.980
     314  dual-evpn  server103  evpnVni       1         []        []       []      []        []                    0 2020-06-17 05:14:38.144
     325  dual-evpn  server103     mlag     404         []        []       []      []        []                    0 2020-06-17 05:14:38.792
     326  dual-evpn  server103   ospfIf       1         []        []       []      []        []                    0 2020-06-17 05:14:38.138
     327  dual-evpn  server103  ospfNbr       1         []        []       []      []        []                    0 2020-06-17 05:14:40.594
     338  dual-evpn  server104      bgp       1         []        []       []      []        []                    0 2020-06-17 05:14:40.980
     341  dual-evpn  server104  evpnVni       1         []        []       []      []        []                    0 2020-06-17 05:14:38.145
     352  dual-evpn  server104     mlag     404         []        []       []      []        []                    0 2020-06-17 05:14:38.792
     353  dual-evpn  server104   ospfIf       1         []        []       []      []        []                    0 2020-06-17 05:14:38.830
     354  dual-evpn  server104  ospfNbr       1         []        []       []      []        []                    0 2020-06-17 05:14:40.980
```
In this case the errors are because we aren't running any of those services on these nodes.


## Database and Data Persistence

Because everything in Suzieq revolves around [Pandas](https://pandas.pydata.org/) dataframes, it can support different persistence engines underneath. For right now, we only support our own, which is built on [Parquet](https://parquet.apache.org/) files. 
This is setup should be fast enough to get things going and for most people. It is also self contained and fairly simple. 
We have tried other storage systems, so we know it can work, but none of that code is production worthy. As we all gain experience we can figure out what the right persistence engines are One of the advantages is that the data are just files that can easily be passed around. There is no database code that must be running before you query the data. 
