# Running the Poller

The simplest way to run the poller is via the docker image.  Launch the docker image and attach to it via the following steps:
- ```docker run -itd -v /home/jpiet/parquet-out:/suzieq/parquet -v /home/jpiet/<ansible-inventory-file>:/suzieq/inventory --name sq-poller ddutt/suzieq:latest```
- ```docker attach sq-poller```

In the docker run command above, the two -v options provide host file/directory access to store the parquet output files (the first -v option), and the Ansible inventory file (the second -v option). If you don't use Ansible or don't want to provide that file, don't worry, you can still use the poller to gather data.

The poller needs the list of the devices and their IP address to gather data from. This list can be supplied in one of two ways: 

* via a Suzieq native YAML format file or 
* via or an Ansible inventory file (supplied via the second -v option above, and available as file /suzieq/inventory inside the docker).

The Suzieq native inventory file format that contains the IP address, the access method (SSH or REST), the IP address of the node, the user name, the type of OS if using REST and the access token such as a private key file. The format looks as follows, for example:
```
- namespace: eos
  hosts:
    - url: https://vagrant@192.168.123.252 devtype=eos
    - url: https://vagrant@192.168.123.213 devtype=eos
    - url: https://vagrant@192.168.123.141 devtype=eos
    - url: ssh://vagrant@192.168.123.232  keyfile=/home/ddutt/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/internet/libvirt/private_key
    - url: https://vagrant@192.168.123.164 devtype=eos
    - url: ssh://vagrant@192.168.123.70  keyfile=/home/ddutt/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server103/libvirt/private_key
    - url: https://vagrant@192.168.123.78 devtype=eos
    - url: ssh://vagrant@192.168.123.230  keyfile=/home/ddutt/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server101/libvirt/private_key
    - url: ssh://vagrant@192.168.123.54  keyfile=/home/ddutt/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server104/libvirt/private_key
    - url: ssh://vagrant@192.168.123.111  keyfile=/home/ddutt/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server102/libvirt/private_key
    - url: https://vagrant@192.168.123.163 devtype=eos
    - url: https://vagrant@192.168.123.185 devtype=eos
    - url: ssh://vagrant@192.168.123.7  keyfile=/home/ddutt/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/edge01/libvirt/private_key
    - url: https://vagrant@192.168.123.123 devtype=eos
```

**This file can be hand-crafted or generated from an Ansible inventory file** via the following python program shipped in the docker image: `/root/.local/lib/python3.7/site-packages/suzieq/genhosts.py`. You invoke the program as follows: 
`python /root/.local/lib/python3.7/site-packages/suzieq/genhosts.py /suzieq/inventory eos.yml eos`.

In the command above, we're assuming the output file is called eos.yml and the *namespace* is called *eos*. `genhosts.py` is somewhat simplistic right now. It assumes we're using REST API for Arista nodes and SSH for everybody else. The Ansible inventory file is the file we mounted during `docker run`.

There's a template in the docs directory called hosts-template.yml. You can copy that file as the template and fill out the values for namespace and url (remember to delete the empty URLs and to not use TABS, some editors add them automatically if the filename extension isn't right). The URL is the standard URL format: <transport>://[username:password]@<hostname or IP>:<port>. For example, ssh://dinesh:dinesh@myvx or ssh://dinesh:dinesh@172.1.1.23. 

Once you have either generated the hosts file or are using the Ansible inventory file, you can launch the poller inside the docker container using **one** of the following two options: 

* If you're using the native YAML hosts file, use the -D option like this: `sq-poller -D eos`  or
* if you're using the Ansible inventory format, use the -i and -n options like this: via `sq-poller -i /suzieq/inventory -n eos`. 

The poller creates a log file called /tmp/sq-poller.log. You can look at the file for errors. The output is stored in the parquet directory specified under /suzieq/parquet and visible in the host, outside the container, via the path specified during docker run above. 

## <a name='gathering-data'></a>Gathering Data
Two important concepts in the poller are Nodes and Services. Nodes are devices of some kind;
they are the object being monitored. Services are the data that is collected and consumed by Suzieq. 
Service definitions describe how to get output from devices and then how to turn that into useful data.

Currently Suzieq supports polling [Cumulus Linux](https://cumulusnetworks.com/),
[Arista](https://www.arista.com/en/),
[Nexus](https://www.cisco.com/c/en/us/products/switches/data-center-switches/index.html),
and (Juniper(https://www.juniper.com) devices, as well as native Linux devices such as servers. Suzieq can easily support other device types, we just haven't had access to those and not time to chase them down.

Suzieq started out with least common denominator SSH and REST access to devices.
It doesn't much care about transport, we will use whatever gets the best data.
Suzieq does have support for agents, such as Kafka and SNMP, to push data and we've done some experiments with them, but don't
have production versions of that code. 

## Database and Data Persistence

Because everything in Suzieq revolves around [Pandas](https://pandas.pydata.org/) dataframes, it can support different persistence engines underneath. For right now, we only support our own, which is built on [Parquet](https://parquet.apache.org/) files. 
This is setup should be fast enough to get things going and for most people. It is also self contained and fairly simple. 
We have tried other storage systems, so we know it can work, but none of that code is production worthy. As we all gain experience we can figure out what the right persistence engines are One of the advantages is that the data are just files that can easily be passed around. There is no database code that must be running before you query the data. 


