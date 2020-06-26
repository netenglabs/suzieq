import typing
from collections import OrderedDict, defaultdict
from itertools import repeat
from dataclasses import dataclass

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from suzieq.sqobjects import interfaces, lldp, bgp, ospf, basicobj, address
from suzieq.sqobjects.basicobj import SqObject
from suzieq.exceptions import NoLLdpError, EmptyDataframeError, PathLoopError

# TODO:
#  redo everything as our own link state database with all the attributes
#     we want, but then turn into Graphs just for analysis and maps
#  can we do this if there isn't LLDP?
#  topology for different VRFs?
#  topology for eVPN / overlay
#  iBGP vs eBGP?
#  color by device type?
#  physical topology without LLDP
#  how to draw multiple topologies
#  be able to ask if a node has neighbors by type (physical, overlay, protocol, etc)
#  questions
#    * without knowing hierarchy, labels or tags it's unclear how to group things
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
        self.nses = self._if_df['namespace'].unique()

    
    def get(self, **kwargs):
        namespaces = kwargs.get("namespace", self.ctxt.namespace)
  
        self.ns = {}
        self._init_dfs(namespaces)
        self.lsdb = pd.DataFrame()

        for i in self.nses:
            self.ns[i] = {}

        self.services = [

            Services('LLDP', lldp.LldpObj, {}, 'peerHostname', 'ifname', None),
            Services('BGP', bgp.BgpObj, {'state': 'Established'},'peerHostname', 
                'peer', None),
            Services('OSPF', ospf.OspfObj, {}, 'peerHostname', 'ifname', 
                self._augment_ospf_show)
            ]
        
        for srv in self.services: 
            
            df = srv.data(context=self.ctxt).get(
                namespace=namespaces, columns=self.columns,
                **srv.extra_args
                ).dropna(how='any')
            
            
            if not df.empty:
                if srv.augment:
                    df = srv.augment(df)
                df = df[['namespace', 'hostname', srv.key, srv.label_col]]
                df[srv.name] = True
                if self.lsdb.empty:
                    self.lsdb = df
                else:
                    self.lsdb = self.lsdb.merge(df, how='left')
                grp = df.groupby(by=['namespace'])

        
        self._create_graphs_from_lsdb()
        self._analyze_lsdb_graph()
        self._make_images()
        # breakpoint()
        # multigraphs = {}
        # for ns in self.nses:
            
        #     gs = []
        #     edge_labels = {}
            
        #     for srv in self.services:
        #         gs.append(self.graphs[srv.name][ns])
                
                
        #     G = nx.compose_all(gs)
        #     for srv in self.services:
        #         edge_labels[srv.name]=nx.get_edge_attributes(self.graphs[srv.name][ns], 'topology')
            
            
        #     pos = nx.spring_layout(G)
        #     nx.draw(G, with_labels=True, pos=pos)
        #     colors = ['r', 'g', 'b']
        #     i = 0
        #     el = defaultdict(list)
        #     for srv, edges in edge_labels.items():
                
        #         for edge, _ in edges.items():
        #             el[edge].append(srv) 
        #     for edge in el:
        #         el[edge] = " ".join(el[edge])    

        #     nx.draw_networkx_edge_labels(G, pos, edge_labels=el, font_size=6)
            
        #     plt.savefig(f"{ns}.png")
        #     plt.close()


        #     multigraphs[ns] = G
        return pd.DataFrame(self.ns)

 
    def _create_graphs_from_lsdb(self):
        self.graphs = {}
        for ns, df in self.lsdb.groupby(by=['namespace']):
            attrs = [srv.name for srv in self.services if srv.name in df.columns]
            self.graphs[ns] = nx.from_pandas_edgelist(df, 'hostname', 'peerHostname', attrs)

    def _analyze_lsdb_graph(self):
        for ns in self.nses:
            for name in [srv.name for srv in self.services if \
                nx.get_edge_attributes(self.graphs[ns], srv.name)]:
                
                G = nx.Graph([(s,d,data) for s,d,data in 
                    self.graphs[ns].edges(data=True) if data[name] == True])
                if G.nodes:
                    self.ns[ns][f'{name}_number_of_nodes'] = len(G.nodes)
                    self.ns[ns][f'{name}_number_of_edges'] = len(G.edges)
                    if not nx.is_connected(G):
                        self.ns[ns][f'{name}_is_fully_connected'] = False
                        self.ns[ns][f'{name}_center'] = False
                    else:
                        self.ns[ns][f'{name}_is_fully_connected'] = True
                        self.ns[ns][f'{name}_center'] = nx.barycenter(G)
                    
                    self.ns[ns][f'{name}_self_loops'] = list(nx.nodes_with_selfloops(G))
                    
                    self.ns[ns][f'{name}_number_of_subgroups'] = len(list(nx.connected_components(G)))
                    
                    self.ns[ns][f'{name}_degree_histogram'] = nx.degree_histogram(G)
                    #self.ns[ns][f'{name}_bridges'] = list(nx.bridges(G))
                else:
                    for k in [f'{name}_is_fully_connected', f'{name}_center',
                        f'{name}_self_loops', f'{name}_number_of_subgroups', 
                        f'{name}_degree_histogram', f'{name}_number_of_nodes',
                        f'{name}_number_of_edges']:
                        self.ns[ns][k] = "N/A"


    def _make_images(self):
        for ns in self.nses:
            pos = nx.spring_layout(self.graphs[ns])
            for name in [srv.name for srv in self.services if \
                nx.get_edge_attributes(self.graphs[ns], srv.name)]: 
                edges = [(u,v) for u,v,d in self.graphs[ns].edges(data=True) if \
                    d[name] == True]
                if len(edges) > 1:    
                
                    nx.draw_networkx_nodes(self.graphs[ns], pos=pos)
                    nx.draw_networkx_labels(self.graphs[ns], pos=pos)
                    
                    nx.draw_networkx_edges(self.graphs[ns], edgelist = edges, pos=pos)
                    plt.savefig(f"{ns}_{name}.png")
                    plt.close()

    # TODO: eventually this needs to move to ospf after we figure out the schema augmentation story
    def _augment_ospf_show(self, df):
        if not df.empty:
            a_df = address.AddressObj(context=self.ctxt).get(columns=self.columns)
            
            if not a_df.empty:
                a_df = a_df[['namespace', 'hostname', 'ipAddressList']]
                a_df = a_df.explode('ipAddressList').dropna(how='any')
                a_df = a_df.rename(columns={'ipAddressList': 'peerIP', 
                'hostname': 'peerHostname'})
                a_df['peerIP'] = a_df['peerIP'].str.replace("/.+", "")

                df = df.merge(a_df, on=['namespace', 'peerIP'], how='left').dropna(how='any')

        return df

        
@dataclass(frozen=True)
class Services:
    name: str
    data: SqObject
    extra_args: dict
    key: str
    label_col: str
    augment: any
