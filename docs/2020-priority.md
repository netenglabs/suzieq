# Suzieq Priorities

(last updated June 2022)

This roadmap represents our best guess at broad priorities. 
The point is to demonstrate what we think we should work on and the general
order of what we want to deliver.  If we are missing something that would make
it more useful to you, please let us know. The best way is to
[file an issue](https://github.com/netenglabs/suzieq/issues/new/choose).

We are trying to provide a mix of adding new collection, new analysis, and making Suzieq a better
platform to build on.

## Areas of Development

There are six major areas that Suzieq development can be broken down into.

1. Platforms (new NOS)
1. Features
   * new tables
   * new services
1. New segments
   * server -- kubernetes
   * isp / WAN
   * enterprise
1. Performance
   * scale
      * devices we poll
      * amount of data polled
1. Usability
   * gui
   * users define own queries
   * user asserts
1. Integration with other systems

## Rough List of Tasks

Given the categories, here is a rough list of tasks we will be tackling. We welcome assistance with any of these tasks. We intend to work our way roughly down this list and so tasks later down the line will be tend to, in general, be worked on later. Some of these tasks are shorter in time and complexity and some are longer. We expect to add more items. Striked out tasks are those that have been done already.

* ~~Anonymizing data -- almost done, needs tests, docs, and moved to master~~
* ~~Junos support for qfx/mx~~
* Building a reference topology to test all NOS (75% done)
~~* Topology as a first class property~~
    ~~* draw a map for physical and logical layers, including routing protocols~~
* neighbor discovery
    ~~* show neighbors that we know about but aren't polling~~
~~    * maybe be able to just start with one IP address and then discover 
      everything that must be polled by suzieq
* ~~support augmenting columns (like adding peerHostname in OSPF when all we have is peerIP)~~
* ~~make column manipulation at higher level than engine.py~~
* ~~Schema evolution and versioning to make suzieq less brittle to changes in the schema~~
~~* Web-based GUI--
--  * ~Do you have a framework you'd like the GUI to use?~~
* ~~REST API~~
* Kubernetes
  * understand topology, pod and cluster
  * calico, cilium, vxlan
  * asserts
* Better unit tests with mocking instead of just end-to-end with real data.
* ~~Arista EVPN~~
* ~~Users can do their own queries~~
  * ~~pandas or pandas sql query~~
~~* Great expectations or some other way of better verifying data output
~~* Better database abstractions so that we can more easily add new databases~~
* ~~Support for SONIC~~
  * This includes SONIC-specific stuff only. Linux-specific and FRR are already supported.
~~* Support for Cisco's CSR1000~~
* ~~Support for Cisco's IOS-XR~~
* Temperature and power collection 
* Cloud integration such as VPC from cloud providers
* BMP to collect BGP data for realtime BGP analysis
* Understand BGP routing policy and route maps / etc
* ISIS
* ~~Supporting 1M+ routes per device~~

## How You Can Help

* By telling us which of these tasks you care to see sooner than later
* Signing up to help with some of the tasks
* Suggesting items that you care about but are missing from this list. The best way to do this is to open an issue. Please do add some color about how you intend to use Suzieq with that feature.
* Writing some tests and/or documentation
* Funding us to do the work :)
