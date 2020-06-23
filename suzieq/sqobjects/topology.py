import typing
from collections import OrderedDict
from itertools import repeat

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from suzieq.sqobjects import interfaces, lldp, bgp, ospf, basicobj, address
from suzieq.exceptions import NoLLdpError, EmptyDataframeError, PathLoopError

# TODO:
#  how do we collect and draw multiple topologies  
#  can we do this if there isn't LLDP?
#  topology for different VRFs?
#  topology for eVPN / overlay
#  bgp topology
#  ospf topology
#  color by device type?
#  be able to ask fi a node has neighbors by type (physical, overlay, protocol, etc)
#  too much duplication between graph creation functions. make it smaller
#  questions
#    * is each topology a different command?
#    * will we want more than one topology at a time?
#    * without knowing hierarchy, labels or tags it's unclear how to group things



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
        """Initialize the dataframes used"""
        
        self._if_df = interfaces.IfObj(context=self.ctxt) \
                                .get(namespace=namespaces)
        
        if self._if_df.empty:
            raise EmptyDataframeError(f"No interface found for {namespaces}")

    
    def get(self, **kwargs):
        namespaces = kwargs.get("namespace", self.ctxt.namespace)
  
        self.ns = {}
        self._init_dfs(namespaces)
        for i in self._if_df['namespace'].unique():
            self.ns[i] = {}

        services = [
            ('LLDP', lldp.LldpObj, 'peerHostname', 'ifname'),
            ('BGP', bgp.BgpObj, 'peerHostname', 'peer' ),
            ('OSPF', ospf.OspfObj, 'peerHostname', 'ifname')
            ]

        for name, obj, key, label_col in services:
            df = obj(context=self.ctxt).get(
                namespace=namespaces, columns=self.columns).dropna(how='any')
            grp = df.groupby(by=['namespace'])
            breakpoint()
            self._create_topology_from_df(df, grp, name, key, label_col)

        return pd.DataFrame(self.ns)
       
    def _create_topology_from_df(self, df, group, label, key, label_col):
        graphs = {}
        for i in self._if_df['namespace'].unique():
            graphs[i] = nx.Graph(name=f"{i}") 
        devices = group['hostname']
        
        for ns, hosts in devices:
            hosts = hosts.unique()
            
            for device in hosts:
                graphs[ns].add_node(device, name=device)
                # TODO: this is too iterative, I need to do this once for the namespace and then figure out how to break things up
                node_df = df.query(f"hostname == '{device}' and namespace == '{ns}'")[
                    [key, label_col]]
                
                for index, row in node_df.iterrows():
                    graphs[ns].add_edge(device, row[key], 
                    ifname=row[label_col], topology=label)
        
        self._analyze_graph(graphs, label)
        self._make_image(graphs, label)
        
        return graphs


    def _make_image(self, graphs, label):

        for name, G in graphs.items():
            if G.nodes:
                nx.draw(G, with_labels=True, pos=nx.spring_layout(G))
                
                plt.savefig(f"{label}_{name}.png")
                plt.close()

    def _analyze_graph(self, graphs, label):

        for name, G in graphs.items():
            if G.nodes:

                if not nx.is_connected(G):
                    self.ns[name][f'{label}_is_fully_connected'] = False
                    self.ns[name][f'{label}_barrycenter'] = False
                else:
                    self.ns[name][f'{label}_is_fully_connected'] = True
                    self.ns[name][f'{label}_barrycenter'] = nx.barycenter(G)
                
                self.ns[name][f'{label}_self_loops'] = list(nx.nodes_with_selfloops(G))
                
                self.ns[name][f'{label}_number_of_subgroups'] = len(list(nx.connected_components(G)))
                
                self.ns[name][f'{label}_degree_histogram'] = nx.degree_histogram(G)
                #self.ns[name][f'{label}_bridges'] = list(nx.bridges(G))
            else:
                for k in [f'{label}_is_fully_connected', f'{label}_barrycenter',
                     f'{label}_self_loops', f'{label}_number_of_subgroups', 
                     f'{label}_degree_histogram']:
                     self.ns[name][k] = "N/A"
            
        

            


