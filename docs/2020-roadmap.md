This roadmap represents our best guess at what we intend to build in 2020. 
The point is to demonstrate what we think we should work on and the general
order of what we want to deliver.  If we are missing something that would make
it more useful to you, please let us know. The best way is to
file an issue in github.


We aren't really sure what our release structure will be. We will 
probably drop some releases quickly with a small number of important
features that we know are blocking people (like other Network OSes).
We aren't really sure what the overall strategy should be.

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

1. platforms (new NOS)
1. features
   * new tables
   * new services
1. new segments
   * server -- kubernetes
   * isp / WAN
   * enterprise
1. performance
   * scale
      * devices we poll
      * amount of data polled
1. useability
   * gui
   * users define own queries
   * user asserts
1. integration with other systems

## Roadmap for the rest of 2020 as of June 

This is our best guess at priority. We are not sure how long these will take, but this is the order we intend as of now. We are also not sure if other things will come up for us this year. Let us know if there are things on this list missing or that you really want.

1. testing and reference topology for use across all NOS
1. GUI
    * what should the GUI be based on
        * streamlit, detail, jupyter, grafana
1. topology as a first class property
    * draw a map for physical and logical layers, including routing protocols
    * neighbor discovery
        * show neighbors that we know about but aren't polling
        * maybe be able to just start with one IP address and then discover 
           everything that must be polled by suzieq
1. schema evolution and versioning and make suzieq less brittle to changes in the schema
1. Arista EVPN
1. Kubernetes
    * understand topology, pod and cluster
    * calico, vxlan, cilium
    * asserts
1. integration with performance analysis
    * integration with promethius and influxdb
    * what do we want to be able to do with this?
1. integration with systems for notification of events
   * slack
   * ???
1. create tags or other ways to group  in a hierarchical way
    * possibly reuse ansible grouping
1. network wide summarize to take advantage of data across all commands    
1. real documentation of our main functions so that we can get 
our APIs documented.

1. Be sure that we can scale to at least 500 nodes per poller instance
1. users can do their own queries
    * pandas or pandas sql query
    * is this only in the GUI?


tech debt other things we need to mix in
* Better separate database abstractions so that we can more easily add new databases
* better unit tests with mocking instead of just end-to-end with real data.
* better unit tests with mocking instead of end-to-end with real data.
* great expectations or some other way of better verifying data output https://docs.greatexpectations.io/en/latest/


## things we are not yet expecting to do
but let us know if you either need this or want to help contribute

By category:

1. platforms
    * IOS XR
    * IOS XE
    * SONIC
1. features
    * temperature and power collection and tracking
    * Cloud integration
    * Kafka integraion for streaming telemetry
1. new segments
    * understand BGP routing policy and route maps / etc
    * ISIS 
    * MPLS
    * ACLs
    * QoS
1. performance
    * Supporting 1M+ routes per device
    * BMP to collect BGP data
    * Cache or even keep DataFrames between queries. right now Suzieq gets data from disk at every query.
    * use a diffrent database such as spark or modin -- we have inital experiments with thse but we'd need to get them up-to-dat
1. usability
    * make asserts more modular and easier to extend
        * We're not sure how this should work, it's just if there are 500
        asserts from 127 people it will be a mess the way it is
        * asserts are ways to build health checks to assure your network is behaving
        as expected even during changes
1. integration with other systems


## We believe users are moving away from: (If you disagree, let us know)

* SNMP access to data

