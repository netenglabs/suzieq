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
representation of what Suzieq can be used for. We know we need
to have more NOSes are necessary. 

(We should scope this either by effort or expected date)

## End of year problems solved
Overall, where we want to be by the end of the year
* support NOSes that most people use
    * Cumulus Linux, Arista EOS, NX OS, JunOS
* understand kubernetes
    * calico, vxlan, cilium
* how is an app spinning up going to effect my network
    * I don't remember how we want to solve this


## Roadmap for the rest of 2020
1. NXOS support -- including EVPN
1. GUI
    * what should the GUI be based on
        * streamlit, detail, jupyter, grafana
1. topology as a first class property
    * draw a map for physical and logical layers, including routing protocols
    * neighbor discovery
        * show neighbors that we know about but aren't polling
        * maybe be able to just start with one IP address and then discover 
           everything that must be polled by suzieq
1. Arista EVPN
1. Kubernetes
    * understand topology, pod and cluster
    * calico, vxlan, cilium
    * asserts
1. create tags or other ways to group probably in a hierarchical way
1. fancy asserts -- what does this mean
1. real documentation of our main functions so that we can get 
our APIs documented.
1. integration with performance analysis
    * integration with promethius and influxdb
    * what do we want to be able to do with this?
1. JunOS
1. BMP to collect BGP data
1. Be sure that we can scale to at least 500 nodes without a problem
1. users can do their own queries
    * pandas or pandas sql query
    * is this only in the GUI?
1. integration with systems for notification of events
   * slack
   * ???



## things we are not yet expecting to do
but let us know if you either need this or what to help contribute
* SONIC
* ISIS
* understand BGP routing policy and route maps / etc
* MPLS
* make asserts more modular and easier to extend
    * We're not sure how this should work, it's just if there are 500
    asserts from 127 people it will be a mess the way it is
* IOSXR
* IOS XE
* temperature and power collection and tracking

