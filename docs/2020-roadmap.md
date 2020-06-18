# DRAFT -- NOT YET AGREED UPON --
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

## End of year problems solved
Overall, where we want to be by the end of the year
* support NOSes that most people use
    * Cumulus Linux, Arista EOS, NX OS, JunOS
* understand kubernetes
    * calico, vxlan, cilium
* how is an app spinning up going to effect my network


## Categories of problems we want to solve
1. platforms
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
1. integration with out systems

## Roadmap for the rest of 2020 as of June 

This is our best guess at priority. We are not sure how long these will take, but this is the order we intend as of now. We are also not sure if other things will come up for us this year. Let us know if there are things on this list missing or that you really want.

1. testing and reference topology
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
    
1. real documentation of our main functions so that we can get 
our APIs documented.

1. Be sure that we can scale to at least 500 nodes without a problem
1. users can do their own queries
    * pandas or pandas sql query
    * is this only in the GUI?


tech debt other things we need to mix in
* not sure how to schedule the bugs and features we are accumulating in issues
* how to separate out database 
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
1. new segments
    * understand BGP routing policy and route maps / etc
    * ISIS 
    * MPLS
    * ACLs
    * QoS
1. performance
    * make sure we can support 1M+ routes per device
    * BMP to collect BGP data
1. useability
    * make asserts more modular and easier to extend
        * We're not sure how this should work, it's just if there are 500
        asserts from 127 people it will be a mess the way it is
        * asserts are ways to build health checks to assure your network is behaving
        as expected even during changes
1. integration with out systems


## We believe users are moving away from: (If you disagree, let us know)

* SNMP access to data

