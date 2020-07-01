from suzieq.engines.pandas.engineobj import SqEngineObject
import typing
from collections import OrderedDict, defaultdict
from itertools import repeat
from dataclasses import dataclass
import os

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from suzieq.sqobjects import interfaces, lldp, bgp, ospf, basicobj, address, evpnVni
from suzieq.sqobjects.basicobj import SqObject
from suzieq.exceptions import NoLLdpError, EmptyDataframeError, PathLoopError

graph_output_dir = '/tmp/suzieq-graphs'

class TopologyObj(SqEngineObject):

    
    def _init_dfs(self, namespaces):
        """Initialize the dataframes used"""
        
        self._if_df = interfaces.IfObj(context=self.ctxt).get(namespace=namespaces)
        
        if self._if_df.empty:
            raise EmptyDataframeError(f"No interface found for {namespaces}")
        self.nses = self._if_df['namespace'].unique()

    
    def get(self, **kwargs):
        namespaces = kwargs.get("namespace", self.ctxt.namespace)
  
        self.ns = {}
        self._init_dfs(namespaces)
        self.lsdb = pd.DataFrame()
        self._a_df = None

        for i in self.nses:
            self.ns[i] = {}

        self.services = [

            Services('lldp', lldp.LldpObj, {}, 'peerHostname', 'ifname', None),
            Services('bgp', bgp.BgpObj, {'state': 'Established'},'peerHostname', 
                'peer', None),
            Services('ospf', ospf.OspfObj, {}, 'peerHostname', 'ifname', 
                self._augment_ospf_show),
            # EVPN doesn't work yet because we don't have the evpn 'link state' that we need
            #Services('evpnVni', evpnVni.EvpnvniObj, {}, 'peerHostname',
            #    'vni', self._augment_evpnvni_show)

            ]
        
        for srv in self.services: 
            
            df = srv.data(context=self.ctxt).get(
                namespace=namespaces,
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
                    self.lsdb = self.lsdb.merge(df, how='outer')
                grp = df.groupby(by=['namespace'])

        
        self._create_graphs_from_lsdb()
        self._analyze_lsdb_graph()
        self._make_images()

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
                    
                    self.ns[ns][f'{name}_number_of_disjoint_sets'] = len(list(nx.connected_components(G)))
                    
                    self.ns[ns][f'{name}_degree_histogram'] = nx.degree_histogram(G)
                    #self.ns[ns][f'{name}_bridges'] = list(nx.bridges(G))
                else:
                    for k in [f'{name}_is_fully_connected', f'{name}_center',
                        f'{name}_self_loops', f'{name}_number_of_disjoint_sets', 
                        f'{name}_degree_histogram', f'{name}_number_of_nodes',
                        f'{name}_number_of_edges']:
                        self.ns[ns][k] = "N/A"


    def _make_images(self):
        if not os.path.exists(graph_output_dir):
            os.makedirs(graph_output_dir)
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
                    plt.savefig(f"{graph_output_dir}/{ns}_{name}.png")
                    print(f"created {graph_output_dir}/{ns}_{name}.png")
                    plt.close()

    # TODO: eventually this needs to move to ospf after we figure out the 
    #   schema augmentation story
    def _augment_ospf_show(self, df):
        if not df.empty:
            df = df.merge(self.address_df, on=['namespace', 'peerIP'], 
                how='left').dropna(how='any')

        return df
    
    def _augment_evpnvni_show(self, df):
        if not df.empty:
            df = df.explode('remoteVtepList').dropna(how='any')
            df = df.rename(columns={'remoteVtepList': 'peerIP'})
            df = df.merge(self.address_df, on=['namespace', 'peerIP'],
                how='left').dropna(how='any')
        return df

    @property
    def address_df(self):
        if self._a_df is None:
            self._a_df = address.AddressObj(context=self.ctxt).get()
            if not self._a_df.empty:
                self._a_df = self._a_df[['namespace', 'hostname', 'ipAddressList']]
                self._a_df = self._a_df.explode('ipAddressList').dropna(how='any')
                self._a_df = self._a_df.rename(columns={'ipAddressList': 'peerIP', 
                    'hostname': 'peerHostname'})
                self._a_df['peerIP'] = self._a_df['peerIP'].str.replace("/.+", "")

        return self._a_df
        
@dataclass(frozen=True)
class Services:
    name: str
    data: SqObject
    extra_args: dict
    key: str
    label_col: str
    augment: any
