# Gather Data From Directory of Command Outputs

If you have a directory of show command outputs from a device and want to use that to update the Suzieq DB instead of using the poller to get the information from a device, you can do it starting with SuzieQ version 0.16.0b1. This page explains the basic steps to do this.

## Folder Structure

The basic directory structure is: <top-level-dir>/<hostname>/show-command-output-files. For example, if you have outputs from your campus say santa-clara for hosts sc-acc-01, sc-acc-02, sc-agg-01 and sc-agg-02. The basic structure you want is:
```
santa-clara/
├── sc-acc-01
│   ├── show_lldp_neighbors_detail.json
│   ├── show_ospf_neighbor_instance_all_detail.json
│   └── show_version.txt
├── sc-acc-02
│   ├── show_lldp_neighbors_detail.json
│   ├── show_ospf_neighbor_instance_all_detail.json
│   └── show_version.txt
├── sc-agg-01
│   ├── show_lldp_neighbors_detail.json
│   ├── show_ospf_neighbor_instance_all_detail.json
│   └── show_version.txt
└── sc-agg-02
    ├── show_lldp_neighbors_detail.json
    ├── show_ospf_neighbor_instance_all_detail.json
    └── show_version.txt
```
The files shown are obviously only a small subset of what we need. The files ending with json are the ones that are served when JSON is requested and the ones ending with .txt are the ones that are supplied when a text format is required. You can refer to the suzieq/config/*.yml set of files for which command outputs and format you need for each NOS and table.

### Having Multiple Instances

If you take multiple snapshots of the show commands, say at 10 am and 10 pm every day, you can create multiple top level directories such as santa-clara-01012022-1000, santa-clara-01012022-2200, santa-clara-01022022-1000 and so on. Under each of these top-level directories you'd reproduce the structure shown above.

### The Minimum Set of Files

Since SuzieQ does automatic device detection, it is imperative that the files needed for SuzieQ to get the relevant information be present in the directories. In most cases, this includes at least: show version, and one or more of other commands. On Cumulus, this additional list includes hostname and cat /proc/uptime, on Junos it includes show system uptime and show system information and so on. 

## Starting Simnodes

Once this directory is created, you must start the simnodes program as follows:
```
sq-simnodes -i santa-clara
```
Assuming santa-clara is in the directory you;re running sq-simnodes from.

This starts multiple SSH servers, one per host under santa-clara, starting at port 10000. Thus, sc-acc-01 is started on port 10000, sc-acc-02 is started on port 10001, sc-agg-01 is started on port 10002 and so on. The directories under santa-clara are sorted before starting the server so the mapping of hostname to SSH port invariant if the host list is not changed. (unless of course you add devices like acc-03 which would be sorted before sc-acc-01 which then would start on port 10000).

## Updating SuzieQ Database

Once this is done, you now need to start the SuzieQ poller to pull data from the SSH simulators to populate the database. For this, you can create a simple inventory file that looks like this (for the santa-clara example above):
```
---
sources:
  - name: simnode_testing
    hosts:
      - url: ssh://vagrant@127.0.0.1:10000 password=vagrant
      - url: ssh://vagrant@127.0.0.1:10001 password=vagrant
      - url: ssh://vagrant@127.0.0.1:10002 password=vagrant
      - url: ssh://vagrant@127.0.0.1:10003 password=vagrant

devices:
  - name: default
    ignore-known-hosts: true
    devtype: iosxe

namespaces:
  - name: testing
    source: simnode_testing
    device: default
```
You can then launch the poller as follows: ```sq-poller -I inventory.yml --run-once-update```. This will run the poller in snapshot mode and update the database. Now you can run the SuzieQ CLI or GUI or any other front end to act on this information.

## Caveats

* REST API to access devices (EOS, for example) is also supported, but has not been as well tested. 
* This model is not a preferred model. It is only for getting users started with SuzieQ so that you can get buy in to run the SuzieQ poller.
