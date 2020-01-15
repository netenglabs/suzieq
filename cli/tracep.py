#!/usr/bin/env python

import sys

from suzieq.sqobjects import interfaces, lldp, routes
import pprint

# src_df = addr.addrObj().get(datacenter=['evpn-dual'], address='10.0.0.11')
# tgt_df = addr.addrObj().get(datacenter=['evpn-dual'], address='10.0.0.100')

datacenter = sys.argv[1]
source = sys.argv[2]
target = sys.argv[3]
dvrf = sys.argv[4]

if_df = interfaces.ifObj().get(datacenter=[datacenter])
src_df = if_df[if_df.ipAddressList.astype(str).str.contains(source+'/')]
tgt_df = if_df[if_df.ipAddressList.astype(str).str.contains(target+'/')]
tgt_host = tgt_df['hostname'].unique()[0]
src_host = src_df['hostname'].unique()[0]
lldp_df = lldp.lldpObj().get(datacenter=[datacenter])
rdf = routes.routesObj().lpm(datacenter=[datacenter], address=target)

if lldp_df[lldp_df['hostname'] == src_host].empty:
    # The source node has no LLDP data, so start from next node, if we can
    raise AttributeError('host with source IP has no LLDP info')

if lldp_df[lldp_df['hostname'] == tgt_host].empty:
    # The target node has no LLDP data, so end with prev node, if we can
    raise AttributeError('host with target IP has no LLDP info')

hosts_iifs = [[src_host, '']]
paths = [src_host]
visited_hosts = set()

# The logic is to loop through the nexthops till you reach the target host
# The topmost while is this looping. The next loop within handles one nexthop
# at a time.The paths are constructed as a list of lists, where each element
# of the outermost loop is one complete path and each inner list represents one
# hop in that path. Each hop is the list of hostname and incoming interface.
# loops are detected by ensuring that no host is visited twice in the same VRF.
# The VRF qualification is required to ensure packets coming back from a
# firewall or load balancer are tagged as duplicates.
while hosts_iifs:
    nexthosts_iifs = []
    newpaths = []
    hosts_this_round = set()

    for host_iif in hosts_iifs:
        host = host_iif[0]
        iif = host_iif[1]
        ivrf = None
        if iif:
            ivrf = if_df[(if_df['hostname'] == host) &
                         (if_df['ifname'] == iif)]['master'] \
                         .to_string(index=False).strip()
        if not ivrf:
            ivrf = dvrf
        skey = host+ivrf

        if skey in visited_hosts:
            # This is a loop
            raise AttributeError('Loop detected on node {}'.format(host))
        hosts_this_round.add(skey)

        if host == tgt_host:
            continue
        rslt = rdf.query('hostname == "{}" and vrf == "{}"'.format(host, ivrf))
        if rslt.empty:
            continue
        oifs = rslt.oifs.iloc[0].tolist()

        newhosts_iifs = []
        for iface in oifs:
            vlan = 0
            # Remove VLAN subinterfaces
            if '.' in iface:
                raw_iface, vlan = iface.split('.')
            else:
                raw_iface = iface

            raw_iface = [raw_iface]
            # Replace bonds with their individual ports
            slaveoifs = if_df[(if_df['hostname'] == host) &
                              (if_df['master'] == raw_iface[0])] \
                              .ifname.tolist()

            if slaveoifs:
                raw_iface = slaveoifs

            # We need only one of the interfaces (multiple entries here are
            # only in case of a bond
            df = lldp_df[(lldp_df['hostname'] == host) &
                         (lldp_df['ifname'] == raw_iface[0])]

            peer_host = df['peerHostname'].to_string(index=False).strip()
            peer_if = df['peerIfname'].to_string(index=False).strip()

            if slaveoifs:
                peer_if_master = if_df[(if_df['hostname'] == peer_host) &
                                       (if_df['ifname'] == peer_if)]['master'].to_string(index=False).strip()
                if peer_if_master:
                    peer_if = peer_if_master

            if vlan:
                peer_if += '.{}'.format(vlan)

            newhosts_iifs.append([peer_host, peer_if])

        if not newhosts_iifs:
            break

        for x in paths:
            if isinstance(x, list) and x[-1][0] != host:
                continue
            for y in newhosts_iifs:
                if isinstance(x, list):
                    z = x + [y]
                    if z not in newpaths:
                        newpaths.append(z)
                else:
                    newpaths.append([x, y])

        for x in newhosts_iifs:
            if x not in nexthosts_iifs:
                nexthosts_iifs.append(x)

    if newpaths:
        paths = newpaths

    visited_hosts = visited_hosts.union(hosts_this_round)
    hosts_iifs = nexthosts_iifs

pp = pprint.PrettyPrinter(indent=4)
pp.pprint(paths)
