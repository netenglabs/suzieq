# Suzieq
Suzieq is an application focused on observability for IP networks: We want you to understand 
your network as a system. Suzieq gathers data and then allows analysis of the data in interesting ways.

Suzieq does multiple things. It collects data from different devices and systems. 
It normalizes the data and then stores it in a vendor independent way. Then it allows analysis of that data.
Suzieq has a pretty novel way of describing how to collect the data via various tools. We want to be
as agnostic as possible so that we can easily get all the necessary data in one place.

What does Suzieq do that is different from just logging into a device and getting the data?
1. It collects data from all devices and puts it in a central place
2. It collects multiple data from each device
3. It collects data from multiple vendors and normalizes to a standard set of data.
4. It collects data over time.

By using each of these dimensions, we can easily build interesting applications that help understand
networks in way that is much easier. We've just gotten started; our applications are only a brief
demonstration of what this approach can bring about. This is a very early release. We have many more ideas 
on what Suzieq can do, but we wanted to get this out
so that people can start using it. And start solving problems in their networks.

With the applications that we build on top of the framework we want to demonstrate a different
and more systematic approach to thinking about networks. We want to show how useful it is to think
of your network holistically. 

Suzieq data is focused on [Pandas DataFrames](https://pandas.pydata.org/pandas-docs/stable/getting_started/dsintro.html)
Everything returned by the analysis engine is a dataframe.

For now, all the analysis are in a CLI. 

We are just getting started with Suzieq. We believe that this is a great platform for observing and understanding your
network. And we've written applications to demonstrate what is possible. Let us know your ideas on how to make things 
better.

# Analysis
Let's jump into what you can do with Suzieq
```
python3 suzieq/cli/suzieq-cli
```
You get a prompt and at the bottom of the screen are some indicators of what Suzieq is up to:
![Suzieq Start](docs/images/suzieq-start.png)
The words in the bottom show specific choices that you can make to filter data.

To get started, it's often a good idea to look at the help. Just type a '?' to get started:
![Suzieq Help](docs/images/suzieq-help.png)
You see the commands that you can use with Suzieq. For each command there are a small number of verbs 
and some filters that you can add. Most commands have at least the 'show','summary', and 'unique' verbs, some 
commands have more.

A important concept in Suzieq is the *namespace*. Since we are datacenter people, we were orignally thinking
of namespace as datacenter, but it can be whatever grouping of devices that you want. At this point
Suzieq cannot build a hierarchy of namespaces. We will add some way to group namespaces together in 
the future.

Let's look at the some data, we'll start with the system data, to get an overview of the system/nodes
that we have data for. This shows that we have data from 14 nodes and some information about each of
system.
![Suzieq device show](docs/images/suzieq-device-show.png)

Another example of the same command, but with Arista EOS devices:
![Suzieq_device_show_eos](docs/images/suzieq-device-show-eos.png)

Each command has completion to help you understand what you can do with the command. 
For instance, interface command shows that it has five verbs that you can use with it.
![Suzieq interface show help](docs/images/suzieq-interface-show-help.png)

## Demo BGP Analysis

Let's look quickly at BGP data. 
![Suzieq bgp](docs/images/suzieq-bgp-show.png)

There's a lot of data there. We just want to look at the ASNs. Let's look at what the ASNs are and
how many there are of each.
![Suzieq unique ASNs](docs/images/suzieq-bgp-unique-asn.png)

To get an overview of BGP in your networks, we have bgp summarize.
![Suzieq_BGP_summarize](docs/images/suzieq-bgp-summarize.png) 
This can be a bit intimidating, as we are trying to represent a lot of information here.
As you can we, we have a column per namespace, though in this example we only have one namespace. We list the number of
ASNs, peerAsns, etc. We also show the number of rows, which are the number of rows in the 
table if you had just done a 'bgp show'. For items that have a count of 3 or less,
we show the entries, and how many there are of each. So in this example network,
there are two VRFs, with default having 32 rows and internet-vrf having 4. If an item has has more than 3 that you'd 
like to examine, you can use the unique verb as mentioned above. For instance, we see from summarize
that there are 9 ASNs, using unique you can see each ASN and how many times it is being used.

Another interesting
concept is shown in v4PfxRx, V4PfxRx, etc, which is if you see three numbers
in a list, then Suzieq is showing you min, max, and median. This is our best
way to help you understand the distribution that you have.


A quick peak at routes, shows that there are 239 routes.
![Suzieq route show](docs/images/suzieq-routes-show.png)

## Demo Path
One of the nice things that we can do with suzieq is show all the different paths
between two endpoints.
![Suzieq_path_show](docs/images/suzieq-path-show.png) This is a little tricky 
to understand. In this example, there are eight differen paths, represented
by their pathid. For each pathid, we then show each hop. As you can see,
we also show the mtu and if it is an overlay.

Path does not yet work in all cases. Some EVPN cases do not work yet.

## Investigate Suzieq Tables

If you want to look at the database more directly, use the table command. There is not always
a single connection between tables in the database and commands that are available. Also, we are 
collecting data in some tables, such as ifCounters that we do not yet have commands for. 
We assume it's better to start getting data and then we can add useful analysis as we go along.

'table show' shows each table in the database and some statistics about each one. 
![Suzie Tables show](docs/images/suzieq-table-show.png)
Suzieq only saves data to the database if there have been changes to the data. So some 
tables will iterate often, and some will not. Some of the tables show data that Suzieq is collecting,
but we do not have analysis for. For instance, we are collecting ifCounters data, but 
there is no way to access that data from the CLI. 

A special table is called sqPoller, and we do have access to that through the CLI. 
It records the work that suzieq poller is doing. At this point it's probably only 
useful for developers.

For each table, you can look at what is in the data and what are the columns that are displayed automatically.
For instance, with BGP we collect a lot more data than we show by default. 

![Suzieq tables describe bgp](docs/images/suzieq-table-describe-bgp.png)
You can always display more columns by adding the columns filter at the end of a show command.
You can use 'columns=*' to get all the columns available for a command, but for bgp that is a lot!


# Getting Data
Two really important concepts in suzieq are Nodes and Services. Nodes are devices of some kind;
they are the object being monitored. Services are the data that is collected and consumed by suzieq. 
Service definitions describe how to get output from devices and then how to turn that into useful data.

Currently Suzieq  supports polling [Cumulus Linux](https://cumulusnetworks.com/) or
 [Arista](https://www.arista.com/en/) devices, as well as Linux. 
Suzieq can easily support other device types, we just haven't had access to those and not time to 
chase them down.
Adding new device types starts by created a new [Service](docs/service-file-format.md).
Services do work work for what we have tested, but we have not tested around the edges of how
services are parsed. 
They might just work for you, but if you run into trouble we can only help a little right now. 

Suzieq started out with least common denominator SSH and REST access to devices. 
Suzieq does have support for agents to push data and we've done some experiments with them, but don't
have production versions of that code. 
# Getting Started
Suzieq requires Python 3.7, so make sure that is installed first.

## Installation with Pipenv
The first way to install Suzieq is to get the code from github
1. git clone: `git clone git@github.com:ddutt/suzieq.git`
2. Suzieq assumes the use of python3.7 which may not be installed on your computer by default. 
Ubuntu 18.04 ships with 3.6 as default, for example. Check your python version with python3 --version. 
If that is different from 3.7, you’ll need to add the python3.7 and 3.7 dev package. 
But, until we can build the different engines separately, we’re stuck with this requirement. 
3. To install python3.7 on Ubuntu18.04, please execute the following command
    ```
    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt install python3.7 python3.7-dev
    ```
4. Install python3-pip if it has not been installed.
    ```
    sudo apt install python3-pip
    ``` 
5. Install pipenv
    ```
    pip3 install --user pipenv
    ```
6. Install suzieq requirements and setup the virtual environment necessary for suzieq
    ```
    cd suzieq
    pipenv install
    ```
7. Once pipenv finishes, you execute `pipenv shell` to login to the virtualenv that suzieq 
will execute in. 
8. Install cyberpandas -- TODO: 
9. TODO What to do about nubia bug 

Suzieq requires that you have a suzieq config file either in '/.suzieq/suzieq-cfg.yml' or '/.suzieq-cfg.yml'.
It looks like:
```
data-directory: /home/jpiet/parquet-out
service-directory: /home/jpiet/suzieq/config
schema-directory: /home/jpiet/suzieq/config/schema
temp-directory: /tmp/suzieq
logging-level: WARNING
```
You need to make sure that service-directory and schema-directory point to the actual code or nothing will work.
## Polling
The poller needs a [list of devices](docs/hosts-file-format.md) to poll. 
If you have a vagrant inventory, we have a utility to read that data and turn it into the file format
that Suzieq needs. 
```
sudo python suzieq/genhosts.py ~/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory dual-bgp dual
```

After installing all the requirements, starting the poller is easy

`python3 suzieq/poller/sq-poller.py -f -H ~/dual-bgp`

# Database and Persistence of data
Because everything in Suzieq revolves around dataframes, it can support different persistence engines underneath. 
For right now, we only support our own, which is built on [Parquet](https://parquet.apache.org/) files. This is setup should be fast enough
to get things going and for most people. We have tried other storage systems, so we know it can work, but none
of that code is production worthy. As we all gain experience we can figure out what the right persistence engines are

One of the advantages is that the data are just files that can easily be passed around. There is no database code
that must be running before you query the data. 



# How time works in suzieq
By default when you use the CLI and you use a command, you will be using 'view=latest'. This is usually
the most useful and what you expect to see. If you want to see all your data, add 'view=all'

# What Can I do with Suzieq
The point and beauty of Suzieq is to get data from your whole system in one place,  to get all 
the data together and to have it over time. Because of this, we can then do more analysis that 
is very hard to do. At this point we don't have a lot of that analysis, we've been focusing on 
getting the core foundations strong.

The path command is probably the best example at this point of gathering the data from all the devices
as well as the data from multiple device commands.

# How to develop with Suzieq

# Faq
TBD