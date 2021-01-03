# Suzieq Priorities

(last updated July 2020)

This roadmap represents our best guess at broad priorities. 
The point is to demonstrate what we think we should work on and the general
order of what we want to deliver.  If we are missing something that would make
it more useful to you, please let us know. The best way is to
[file an issue](https://github.com/netenglabs/suzieq/issues/new/choose).

We are trying to provide a mix of adding new collection, new analysis, and making Suzieq a better
platform to build on.

So far Suzieq is focused on datacenter, but we if we hear of 
interest in the ISP/WAN space (or any other), then we can pivot
towards that. There's nothing inherent in Suzieq that makes it just 
for one part of the network than the others, we just started in the 
datacenter. The current version will be useful anywhere, it's just 
that we aren't collecting everything we'd need to do a great job
in other places and we don't have asserts tuned towards other use cases.

First release (0.1), was focused on good fundamentals and a good 
representation of what Suzieq can be used for. Second release (0.2)
was focused on NXOS and Junos support.

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

Given the categories, here is a rough list of tasks we will be tackling. We welcome assistance with any of these tasks. We intend to work our way roughly down this list and so tasks later down the line will be tend to, in general, be worked on later. Some of these tasks are shorter in time and complexity and some are longer. We expect to add more items.

* ~~Anonymizing data -- almost done, needs tests, docs, and moved to master~~
* ~~Junos support for qfx/mx~~
* Building a reference topology to test all NOS (75% done)
* Topology as a first class property
  * draw a map for physical and logical layers, including routing protocols
  * neighbor discovery
    * show neighbors that we know about but aren't polling
    * maybe be able to just start with one IP address and then discover 
      everything that must be polled by suzieq
* support augmenting columns (like adding peerHostname in OSPF when all we have is peerIP) 
* change gen_schema to ignore _ fields
* ~~make column manipulation at higher level than engine.py~~
* ~~Schema evolution and versioning to make suzieq less brittle to changes in the schema~~
* Network wide summarize to take advantage of data across all commands
~~* Web-based GUI
  * Do you have a framework you'd like the GUI to use? 
  * For what functions would you use a GUI?
  * caching and performance
~~* suzieq as a daemon
  * do we need suzieq as a daemon -- what are the use cases
* ~~REST API~~
* Create tags or other ways to group  in a hierarchical way
  * possibly reuse ansible grouping
* Kubernetes
  * understand topology, pod and cluster
  * calico, cilium, vxlan
  * asserts
* Better unit tests with mocking instead of just end-to-end with real data.
* Integration with performance analysis
  * integration with promethius and influxdb
  * what do we want to be able to do with this?
* Arista EVPN
* Integration with systems for notification of events
  * slack   * ???
* Be sure that we can scale to at least 500 nodes per poller instance
* Users can do their own queries
  * pandas or pandas sql query
  * is this only in the GUI?
* Great expectations or some other way of better verifying data output <https://docs.greatexpectations.io/en/latest/>
* Better database abstractions so that we can more easily add new databases
* ~~Support for SONIC~~
  * This includes SONIC-specific stuff only. Linux-specific and FRR are already supported.
* Support for Cisco's CSR1000
* Support for Cisco's IOS-XR
* Temperature and power collection 
* Cloud integration such as VPC from cloud providers
* Kafka integraion for streaming telemetry
* Redundancy -- some way of making sure that one poller is always running
* BMP to collect BGP data for realtime BGP analysis
* Understand BGP routing policy and route maps / etc
* ISIS
* ~~Supporting 1M+ routes per device~~
* Make asserts more modular and customizable
  * Asserts are ways to build health checks to assure your network is behaving as expected. We think asserts are a powerful tool in Suzieq's arsenal. 
  * If you have ideas on what asserts you'd like or what problems you'd like asserts to solve, please file an issue so that we can gather more ideas on how to make asserts great.
* Integration with other systems as both source of data and as a client.

## How You Can Help

* By telling us which of these tasks you care to see sooner than later
* Signing up to help with some of the tasks
* Suggesting items that you care about but are missing from this list. The best way to do this is to open an issue. Please do add some color about how you intend to use Suzieq with that feature.
* Writing some tests and/or documentation
* Funding us to do the work :)

