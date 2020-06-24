import typing
from collections import OrderedDict, defaultdict
from itertools import repeat

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from suzieq.sqobjects import interfaces, lldp, bgp, ospf, basicobj, address
from suzieq.exceptions import NoLLdpError, EmptyDataframeError, PathLoopError

# TODO:
#  redo everything as our own link state database with all the attributes
#     we want, but then turn into Graphs just for analysis and maps
#  can we do this if there isn't LLDP?
#  topology for different VRFs?
#  topology for eVPN / overlay
#  color by device type?
#  how to draw multiple topologies
#  be able to ask if a node has neighbors by type (physical, overlay, protocol, etc)
#  questions
#    * is each topology a different command?
#    * will we want more than one topology at a time?
#    * without knowing hierarchy, labels or tags it's unclear how to group things
#    * should I make my own link state database and then at the end put that into graphs? 
#       that way I can decide what data goes where
# how could we add state of connection (like Established) per protocol



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
        nses = self._if_df['namespace'].unique()
        for i in nses:
            self.ns[i] = {}

        services = [
            ('LLDP', lldp.LldpObj, {}, 'peerHostname', 'ifname'),
            ('BGP', bgp.BgpObj, {'state': 'Established'},'peerHostname', 'peer' ),
            ('OSPF', ospf.OspfObj, {}, 'peerHostname', 'ifname')
            ]

        self.graphs = {}
        
        for srv, obj, extra_args, key, label_col in services:     
            df = obj(context=self.ctxt).get(
                namespace=namespaces, columns=self.columns,
                **extra_args
                ).dropna(how='any')
            if not df.empty:
                grp = df.groupby(by=['namespace'])
            
                self.graphs[srv] = self._create_topology_from_df(df, grp, srv, key, label_col)
            else:
                print(f"EMPTY DF for {srv}")
                self.graphs[srv] = self._create_empty_graphs_per_namespace(nses)
        
        multigraphs = {}
        for ns in nses:
            
            gs = []
            edge_labels = {}
            
            for srv, _, _, _, _ in services:
                gs.append(self.graphs[srv][ns])
                
                
            G = nx.compose_all(gs)
            for srv, _, _, _, _ in services:
                edge_labels[srv]=nx.get_edge_attributes(self.graphs[srv][ns], 'topology')
            
            pos = nx.spring_layout(G)
            nx.draw(G, with_labels=True, pos=pos)
            colors = ['r', 'g', 'b']
            i = 0
            el = defaultdict(list)
            for srv, edges in edge_labels.items():
                
                for edge, _ in edges.items():
                    el[edge].append(srv) 
            for edge in el:
                el[edge] = " ".join(el[edge])    

            nx.draw_networkx_edge_labels(G, pos, edge_labels=el, font_size=6)
            
            plt.savefig(f"{ns}.png")
            plt.close()


            multigraphs[ns] = G
        return pd.DataFrame(self.ns)

    def _create_empty_graphs_per_namespace(self, namespaces):
        graphs = {}
        for ns in namespaces:
            graphs[ns] = nx.Graph()
        return graphs
       
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
                    topology=label)
        
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
                self.ns[name][f'{label}_number_of_nodes'] = len(G.nodes)
                self.ns[name][f'{label}_number_of_edges'] = len(G.edges)
                if not nx.is_connected(G):
                    self.ns[name][f'{label}_is_fully_connected'] = False
                    self.ns[name][f'{label}_center'] = False
                else:
                    self.ns[name][f'{label}_is_fully_connected'] = True
                    self.ns[name][f'{label}_center'] = nx.barycenter(G)
                
                self.ns[name][f'{label}_self_loops'] = list(nx.nodes_with_selfloops(G))
                
                self.ns[name][f'{label}_number_of_subgroups'] = len(list(nx.connected_components(G)))
                
                self.ns[name][f'{label}_degree_histogram'] = nx.degree_histogram(G)
                #self.ns[name][f'{label}_bridges'] = list(nx.bridges(G))
            else:
                for k in [f'{label}_is_fully_connected', f'{label}_center',
                     f'{label}_self_loops', f'{label}_number_of_subgroups', 
                     f'{label}_degree_histogram', f'{label}_number_of_nodes',
                     f'{label}_number_of_edges']:
                     self.ns[name][k] = "N/A"
            
        

            


