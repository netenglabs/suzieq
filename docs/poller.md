# Gathering Data: Poller

To gather data from your network, you need to run the poller. We support gathering data from Arista EOS, Cisco IOS, IOS-XE, and IOS-XR platforms, Cisco's NXOS, Cumulus Linux, Juniper's Junos(QFX, EX, MX and SRX platforms), Palo Alto's Panos (version 8.0 or higher, see the  [guide](./panos-support.md) and SoNIC devices, besides Linux 
To start, launch the docker container, **netenglabs/suzieq:latest** and attach to it via the following steps:

```
  docker run -it -v /home/${USER}/parquet-out:/home/suzieq/parquet -v /home/${USER}/<inventory-file>:/home/suzieq/inventory.yml --name sq-poller netenglabs/suzieq:latest
```

In the docker run command above, the two `-v` options provide host file/directory access to (I) store the parquet output files (the first `-v` option), and (II) the inventory file (the second `-v` option). The inventory file is the list of devices and their IP address that you wish to gather data from.

You then launch the poller via the command line:

```bash
  sq-poller -I inventory.yml
```

The inventory file format is covered in the [inventory page](./inventory.md).

To monitor the status of the poller, you can look at the log files created (by default) in the `/tmp` directory. All the aspects related to the creation/update of the inventory are logged into `sq-poller-controller.log`, while the each worker logs into `sq-poller-<x>.log` where `x` is the worker id.

!!! warning
    If you want to start the poller process as background task, remember to redirect the stdout to `/dev/null` otherwise the poller might crash when it tries to write something on the terminal.<br>
    `sq-poller -I inventory.yml >/dev/null &`

## Polling Modes

SuzieQ poller can run in either **continuous mode** or **snapshot mode**. In continuous mode, the poller runs forever, gathering data at the specified period from the supplied inventory file. Alternately, it can run in snapshot mode where it gathers the data just once and stops once it has gathered data from all the nodes in the inventory file. If we cannot gather data from a node, we do not persist in gathering data in the snapshot mode.

The default mode is the continuous mode. To use the snapshot mode, add the option `--run-once=update`.

## <a name='poller-architecture'></a>Poller architecture

|![](images/sq-poller.png)
|:--:|
| Figure 1: Poller architecture  |

The poller is the component in charge of periodically collecting the data from the devices. The list of nodes to poll comes from multiple sources, which are specified in the inventory file, given to the poller as input. The node lists coming from the sources are collected into a single global inventory, which could be splitted into multiple chunks and assigned to a different _worker_, the component in charge of polling the devices. The number of workers to use can be specified via the `-w <n_workers>` argument. For example, the poller could be launched with 2 workers polling the devices:

```shell
sq-poller -I inventory -w 2
```

Some of the sources could be _dynamic_ (i.e. Netbox), this means that the node list might change in time. The poller is able to dynamically track these changes and to provide the new inventory chunks to the workers.

### Inventory chunking

The poller could use different policies for the inventory splitting. At the moment two are supported:

- `sequential`: in this case the inventory is splitted into `n` equal chunks, where `n` is the number of workers.
- `namespace`: nodes can be groupped into namespaces, for example the nodes inside the same namespace can be the devices inside the same data center. This option avoids that nodes from the same namespace end into different chunks. In order to have a worker for each namespace, the number of workers must be equal to the number of namespaces in the inventory.

!!! warning
    At the moment, when using the namespace policy, you should make sure that the number of workers is less or equal than the number of namespaces.

The chunking policy can be easily specified in the SuzieQ configuration file via the `policy` field under chunker in poller:

```yaml
poller:
  chunker:
     policy: sequential
```

### How Many Workers??

An often asked question is how many workers are necessary for any given network. The answer depends on many factors such as the size of the data being pulled, the frequency of the polling, how long each device takes to respond and so on. Some users with a powerful CPU (16 cores, newer processor etc.) have been using a single worker with up to 600 devices while others have had to run a worker per 30 or so devices for the same polling interval.

A **minimal rule of thumb would be no more than 40 devices per worker** assuming a modern device (NXOS, EOS, Cumulus etc.) in a data center environment with EVPN.

A **simple way to check if more workers are needed** is to examine the output of ```sqPoller show poll-period-exceeded=True``` with the appropriate parameters of namespace and hostname. This shows devices whose total gathering plus processing time is exceeding the polling period (default is 1 minute). An examination of the gatherTime column of ```sqPoller show service=<service name>``` reveals the time it takes us to retrieve the data from the device once we send the command over. An examination of the totalTime column reveals how long it takes SuzieQ to gather, parse, normalize and compute the differences from the previous fetch.

**A quick way to get a measure of things** is to run the poller in the snapshot mode (use ```--run-once=update``` option with the poller) where it gathers the data just once and terminates. For example, with an inventory file called inventory.yml, if you launch the poller as ```time sq-poller -I inventory.yml --run-once=update``` and assuming no user input is necessary (such as typing a password), the output reveals roughly how long it takes to discover, and gather the data from all of the devices just once. An examination of the totalTime per service reveals what a normal polling interval ought to be.

Also look at the device's CPU utilization to see the cost of observing the data just once. You can always alter the polling frequency of each service by modifying the period value (or adding a key-value such as ``period: 300`` to the service config file). These files are typically found under the config directory of wherever suzieq happens to be installed. See the devconfig.yml file under the config directory for an example of adding a period.

You can also run multiple pollers each with a different inventory (be very careful to not mix up the device list) and different suzieq-cfg.yml files, each containing a different default polling period, but using the same data-directory to ensure you have all the data in one place. For example, you can put all your JunOS devices in one inventory and monitor it with a different polling period compared to say Cumulus devices.

## <a name='gathering-data'></a>Gathering Data

Two important concepts in the poller are Nodes and Services. Nodes are devices of some kind;
they are the object being monitored. Services are the data that is collected and consumed by SuzieQ.
Service definitions describe how to get output from devices and then how to turn that into useful data.

Currently SuzieQ supports polling [Arista](https://www.arista.com/en/),
[Cisco's IOS](https://www.cisco.com/c/en/us/products/ios-nx-os-software/ios-technologies/index.html) including IOS Classic, IOS-XE and IOS-XR,
[Cisco's NXOS](https://www.cisco.com/c/en/us/products/switches/data-center-switches/index.html),
[Cumulus Linux](https://cumulusnetworks.com/),
[Juniper](https://www.juniper.net),
and [SONIC](https://azure.github.io/SONiC/) and [Palo Alto Firewalls](https://www.paloaltonetworks.com/) devices, as well as native Linux devices such as servers. SuzieQ can easily support other device types, and we have third-party contributors working on other NOSes. Please let us know if you're interested in SuzieQ supporting other NOSes.

SuzieQ started out with least common denominator SSH and REST access to devices.
It doesn't care much about transport, we will use whatever gets the best data.
SuzieQ does have support for agents, such as Kafka and SNMP, to push data and we've done some experiments with them, but don't
have production versions of that code.

## Polling Period

When polling in continuous mode, SuzieQ uses the default period specified in the suzieq-cfg.yml [configuration file](./config_file.md) (you can change the default location via the `-c` option when launching the poller).

Independent of this, you can change the polling period of any individual service by modifying (or adding) the `period:<time in secs>` key-value pair to the service configuration file (located under lib/python\<python version\>/site-packages/suzieq/config) wherever SuzieQ is installed.

## Debugging poller issues

There are two places to look if you want to know what the poller is up to. The first is the poller
log file in */tmp/sq-poller.log*. The second is in SuzieQ in the sq-poller table. We keep data about how
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

In this case the errors are because we aren't running any of those services (mlag, evpn etc.) on those nodes (server101, edge01 etc.).

## Database and Data Persistence

SuzieQ persists data using the popular open source [Apache Parquet](https://parquet.apache.org/) format. The data is compressed and stored very efficiently. No support is provided in the open source edition for throwing away old data. The data is retained forever. There aren't any checks around how full the disk is and so on.
