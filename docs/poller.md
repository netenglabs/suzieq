# Gathering Data: Poller

To gather data from your network, you need to run the poller. Launch the docker container, netenglabs/suzieq:latest and attach to it via the following steps:

- ```docker run -itd -v /home/${USER}/parquet-out:/suzieq/parquet -v /home/${USER}/<inventory-file>:/suzieq/inventory --name sq-poller netenglabs/suzieq:latest```
- ```docker attach sq-poller```

In the docker run command above, the two -v options provide host file/directory access to (i) store the parquet output files (the first -v option), and (ii) the inventory file (the second -v option). We describe the inventory file below. The inventory file is the list of devices and their IP address that you wish to gather data from. 

You then launch the poller via the command line:

- ```sq-poller -D inventory```

To monitor the status of the poller, you can look at /tmp/sq-poller.log file.

The inventory file that the poller uses can be supplied either:

* via a Suzieq native YAML format file (use the -D option as above) or 
* via or an Ansible inventory file (instead of -D, use -a option along with -n). This file has to be the output of ```ansible-inventory --list``` command

The Suzieq native inventory file format that contains the IP address, the access method (SSH or REST), the IP address of the node, the user name, the type of OS if using REST and the access token such as a private key file. The format looks as follows, for example (all possible combinations are shown for illustration):
```
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

There's a template in the docs directory called hosts-template.yml. You can copy that file as the template and fill out the values for namespace and url (remember to delete the empty URLs and to not use TABS, some editors add them automatically if the filename extension isn't right). The URL is the standard URL format: <transport>://[username:password]@<hostname or IP>:<port>. For example, ssh://dinesh:dinesh@myvx or ssh://dinesh:dinesh@172.1.1.23. 

If you're using Ansible to configure the devices, an alternate to the native Suzieq inventory format is to use an Ansible inventory format. The file to be used is the output of the ```ansible-inventory --list``` command. 

Once you have either generated the hosts file or are using the Ansible inventory file, you can launch the poller inside the docker container using **one** of the following two options: 

* If you're using the native YAML hosts file, use the -D option like this: `sq-poller -D eos`  or
* if you're using the Ansible inventory format, use the -a and -n options like this: via `sq-poller -a /suzieq/inventory -n eos`. 

The poller creates a log file called /tmp/sq-poller.log. You can look at the file for errors. The output is stored in the parquet directory specified under /suzieq/parquet and visible in the host, outside the container, via the path specified during docker run above. 

## <a name='ssh-options'></a>SSH Security Options

If you're using SSH to connect to the devices (only Arista EOS uses the REST API), then there maybe various additional options you may want to specify to connect to the device. Here are the options supported by the poller:

* Jumphost use
  : You can use the -j option to specify connection via a jumphost. The parameter specified with -j has the format: ```//<username>@<jumphost>:<port>```. Jumphost support is via a private key file, with the same characteristics as the private key file to connect to the remote devices. For example, if you need to use a passphrase for the private key file to the device, you'll have to use the same passphrase to connect to the device as well.
* Ignore host key authentication
  : This is the equivalent of "StrictHostKeyChecking=no UserKnownHostsFile=/dev/null" ssh options. You can enable this via the -k command line option when starting sq-poller
* Passphrase with Private Key File
  : Some operators have a passphrase associated with the private key file, a more secure model. To enable sq-poller to prompt for this passphrase, use the "--passphrase" option. You'll be prompted for the password.
* SSH Config file
  : Some operators choose to put everything in the ssh config file and expect the SSH client to honor this configuration. You can specify the ssh config file via the  "--ssh-config-file" option. 

## <a name='rest-security'></a>REST Security

With REST API, the only supported authentication at present is username and password.

## <a name='gathering-data'></a>Gathering Data
Two important concepts in the poller are Nodes and Services. Nodes are devices of some kind;
they are the object being monitored. Services are the data that is collected and consumed by Suzieq. 
Service definitions describe how to get output from devices and then how to turn that into useful data.

Currently Suzieq supports polling [Cumulus Linux](https://cumulusnetworks.com/),
[Arista](https://www.arista.com/en/),
[Nexus](https://www.cisco.com/c/en/us/products/switches/data-center-switches/index.html),
and [Juniper](https://www.juniper.net) and SONIC devices, as well as native Linux devices such as servers. Suzieq can easily support other device types, and we have third-party contributors working on other NOSes. Please let us know if you're interested in Suzieq supporting other NOSes.

Suzieq started out with least common denominator SSH and REST access to devices.
It doesn't much care about transport, we will use whatever gets the best data.
Suzieq does have support for agents, such as Kafka and SNMP, to push data and we've done some experiments with them, but don't
have production versions of that code. 

## Debugging poller issues
There are two places to look if you want to know what the poller is up to. The first is the poller
log file in /tmp/sq-poller.log. The second is in Suzieq in the sq-poller table. We keep data about how
polling is going in that table. If you do  suzieq-cli sqpoller show --status=fail you should see any failures.

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


