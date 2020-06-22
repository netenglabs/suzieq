import typing
from collections import OrderedDict
from itertools import repeat

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from suzieq.sqobjects import interfaces, lldp, routes, arpnd, macs, basicobj
from suzieq.exceptions import NoLLdpError, EmptyDataframeError, PathLoopError

# TODO:
#  start with LLDP topology, which is efectively physical topology
#  do analysis, 
#   What is not connected to the rest of the graph
#   what are edges to nodes we don't know about
#  draw map
#   
#  can we do this if there isn't LLDP?
#  topology for different VRFs?
#  topology for eVPN / overlay
#  bgp topology
#  ospf topology
#  be able to ask fi a node has neighbors by type (physical, overlay, protocol, etc)
#  questions
#    * is each topology a different command?
#    * will we want more than one topology at a time?
#    * without knowing hierarchy, labels or tags it's unclear how to group things
# rather than require a namespace, do it per namespace


class TopologyObj(basicobj.SqObject):
    def __init__(
            self,
            engine: str = "",
            hostname: typing.List[str] = [],
            start_time: str = "",
            end_time: str = "",
            view: str = "latest",
            namespace: typing.List[str] = [],
            columns: typing.List[str] = ["default"],
            context=None,
    ) -> None:
        super().__init__(
            engine,
            hostname,
            start_time,
            end_time,
            view,
            namespace,
            columns,
            context=context,
            table=None,
        )
        self._sort_fields = ["namespace", "hostname"]
        self._cat_fields = []

    def _init_dfs(self, namespaces):
        """Initialize the dataframes used in this path hunt"""
        
        self._if_df = interfaces.IfObj(context=self.ctxt) \
                                .get(namespace=namespaces)
        
        if self._if_df.empty:
            raise EmptyDataframeError(f"No interface found for {namespaces}")

        self._lldp_df = lldp.LldpObj(context=self.ctxt).get(
            namespace=namespaces, columns=self.columns)
        if self._lldp_df.empty:
            raise NoLLdpError(f"No LLDP information found for {namespaces}")

        # We ignore the lack of ARPND for now
        self._arpnd_df = arpnd.ArpndObj(
            context=self.ctxt).get(namespace=namespaces)

        self._macsobj = macs.MacsObj(context=self.ctxt, namespace=namespaces)
    
        self._if_grp = self._if_df.groupby(by=['namespace'])
        self._lldp_grp = self._lldp_df.groupby(by=['namespace'])
        self._arpnd_grp = self._arpnd_df.groupby(by=['namespace'])
    
    def get(self, **kwargs):
        namespaces = kwargs.get("namespace", self.ctxt.namespace)
        self._create_lldp_topology(namespaces)
        return pd.DataFrame(self.ns)


    def _create_lldp_topology(self, namespaces):
        self._init_dfs(namespaces)
        self.ns = {}
        self.lldp_graphs = {}
        for i in self._lldp_df['namespace'].unique():
            self.ns[i] = {}
            self.lldp_graphs[i] = nx.Graph(topology='LLDP', name=f"{i}") 
        
        devices = self._lldp_grp['hostname']

        for ns, hosts in devices:
            hosts = hosts.unique()
            for device in hosts:
                self.lldp_graphs[ns].add_node(device, name=device)
                node_df = self._lldp_df.query(f"hostname == '{device}' and namespace == '{ns}'")[
                    ['peerHostname', 'ifname']]
                
                for index, row in node_df.iterrows():
                    self.lldp_graphs[ns].add_edge(device, row['peerHostname'], ifname=row['ifname'] )

        self._analyze_graph(self.lldp_graphs)
        self._make_image(self.lldp_graphs)
        
        
    def _make_image(self, graphs):
        for name, G in graphs.items():
            nx.draw(G, with_labels=True, pos=nx.spring_layout(G))
            
            plt.savefig(f"{name}.png")
            plt.close()

    def _analyze_graph(self, graphs):
        #breakpoint()

        for name, G in graphs.items():
            self.ns[name] = {}
            if not nx.is_connected(G):
                self.ns[name]['is_fully_connected'] = False
                self.ns[name]['barrycenter'] = False
            else:
                self.ns[name]['is_fully_connected'] = True
                self.ns[name]['barrycenter'] = nx.barycenter(G)
            
            self.ns[name]['self_loops'] = list(nx.nodes_with_selfloops(G))
            
            self.ns[name]['number_of_subgroups'] = len(list(nx.connected_components(G)))
            
            self.ns[name]['degree_histogram'] = nx.degree_histogram(G)
            self.ns[name]['bridges'] = list(nx.bridges(G))
            self.ns[name]['number_of_cycles'] = len(nx.cycle_basis(G))
        

            


