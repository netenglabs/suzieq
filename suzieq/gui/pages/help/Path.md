
# Help on Using Path

### Quick Help

You can hover the nodes and links of the graph to get additional help. 

* **Hovering** the mouse over a node shows a table with a count of the failures of key resources associated with that node such as interfaces, BGP and OSPF peering session, and so on
* **Hovering** the mouse over the link connecting two hops, especially on the arrow, shows you various key parameters about that hop such as if the lookup is L2 or L3 or EVPN, the IP address used to lookup the routing table and so on
* **Clicking** on a node takes you to a page that shows the various forwardiing tables used on the node to determine the next hop
* **Clicking** on a link takes you to a page that shows the various forwarding tables used on the node to determine that specific path.

## Introduction

Path is Suzieq simulates an idealized packet flow through the network that Suzieq has data about. It supports:
* L2 hops
* L3 hops
* EVPN/VXLAN hops

Besides this, it supports:
* ECMP
* MTU match per hop
* Determining the Path MTU
* Detecting loops and other errors

Path in Suzieq assumes standard L2/L3 forwarding i.e. on each hop, it:
* Does a routing table lookup in the appropriate VRF to determine nexthops
* Looks up ARP/ND tables to determine the next hop MAC 
* Looks up MAC address table for bridged interfaces to determine correct outgoing interface
* If the route is tunnelled (supports only VXLAN right now), it looks up the remote VTEP IP in the routing table to figure out the path through the underlay

Path only works within a single namespace at this time.

## Page Layout

The page has several different pieces of information. The sidebar is all about getting user input and the main window is all about displaying the path data.

The main portion of the window has the following pieces of information:

* Path Summary
* Graphical view of the path from source to destination
* Tables for each of the failed resources (devices, interfaces, protocols)
* Path in tabular format


