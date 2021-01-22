from .engineobj import SqPandasEngine
import typing
from dataclasses import dataclass
import os

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from suzieq.sqobjects import interfaces, lldp, bgp, ospf, basicobj, address, evpnVni, arpnd, device, macs
from suzieq.sqobjects.basicobj import SqObject
from suzieq.exceptions import EmptyDataframeError


# TODO:
#  topology for different VRFs?
#  iBGP vs eBGP?
#  color by device type?
#  physical topology without LLDP -- is this possible?
#  how to draw multiple topologies
#  be able to ask if a node has neighbors by type (physical, overlay, protocol, etc)
#  questions
#    * without knowing hierarchy, labels or tags it's unclear how to group things for good picture
# how could we add state of connection (like Established) per protocol

graph_output_dir = '/tmp/suzieq-graphs'


class TopologyObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'topology'

    def _init_dfs(self, namespaces):
        """Initialize the dataframes used"""

        self._if_df = interfaces.IfObj(
            context=self.ctxt).get(namespace=namespaces)

        if self._if_df.empty:
            raise EmptyDataframeError(f"No interface found for {namespaces}")
        self.nses = self._if_df['namespace'].unique()

    def get(self, **kwargs):
        self._namespaces = kwargs.get("namespace", self.ctxt.namespace)

        self._init_dfs(self._namespaces)
        self.lsdb = pd.DataFrame()
        self._a_df = pd.DataFrame()
        self._ip_table = pd.DataFrame()
        polled_neighbor = kwargs.pop('polled_neighbor', None)

        self.services = [
            Services('aprnd', arpnd.ArpndObj, {}, ['ifname'],
                     self._augment_arpnd_show),
            Services('bgp', bgp.BgpObj, {'state': 'Established',
                                         'columns': ['*']},
                     ['vrf'],
                     self._augment_bgp_show),
            # Services('evpnVni', evpnVni.EvpnvniObj, {}, 'peerHostname',
            #    'vni', self._augment_evpnvni_show),
            Services('lldp', lldp.LldpObj, {}, ['ifname'],
                     self._agument_lldp_show),
            Services('ospf', ospf.OspfObj, {}, ['ifname', 'vrf'],
                     self._augment_ospf_show),
        ]

        key = 'peerHostname'
        for srv in self.services:
            df = srv.data(context=self.ctxt).get(
                **kwargs,
                **srv.extra_args
            )

            if not df.empty:
                if srv.augment:
                    df = srv.augment(df)
                cols = ['namespace', 'hostname', key]
                if srv.extra_cols:
                    cols = cols + srv.extra_cols
                df = df[cols]
                df.insert(len(df.columns), srv.name, True)
                if self.lsdb.empty:
                    self.lsdb = df
                else:
                    self.lsdb = self.lsdb.merge(df, how='outer')

        self._find_polled_neighbors(polled_neighbor)
        self.lsdb = self.lsdb[~self.lsdb.hostname.isna()].drop_duplicates()

        return self.lsdb

    def _find_polled_neighbors(self, polled_neighbor):
        devices = device.DeviceObj(context=self.ctxt).get(namespace=self._namespaces,
                                                          columns=['namespace', 'hostname'])
        devices = devices[['namespace', 'hostname']].rename(
            columns={'hostname': 'peerHostname'})
        self.lsdb = self.lsdb.merge(devices, how='outer',
                                    indicator=True)
        self.lsdb = self.lsdb.rename(columns={'_merge': 'polled_neighbor'})
        self.lsdb.polled_neighbor = self.lsdb.polled_neighbor == 'both'

        if polled_neighbor != '' and polled_neighbor is not None:
            self.lsdb = self.lsdb[self.lsdb.polled_neighbor == polled_neighbor]

    def _create_graphs_from_lsdb(self):
        self.graphs = {}
        for ns, df in self.lsdb.groupby(by=['namespace']):
            attrs = [srv.name for srv in self.services if srv.name in df.columns]
            self.graphs[ns] = nx.from_pandas_edgelist(
                df, 'hostname', 'peerHostname', attrs, nx.MultiGraph)

    # TODO: eventually this needs to move to ospf after we figure out the
    #   schema augmentation story
    def _augment_ospf_show(self, df):
        if not df.empty:
            df = df.merge(self.ip_table, on=['namespace', 'peerIP'],
                          how='left').dropna(how='any')

        return df

    def _agument_lldp_show(self, df):
        if not df.empty:
            df = df[df.peerHostname != '']
        return df

    def _augment_bgp_show(self, df):
        if not df.empty:
            pass
            df['ifname'] = df['ifname'].str.replace('None', '', regex=False)
            df['ifname'] = df['ifname'].str.replace(
                'loopback\d*', '', regex=True)
            df = df.rename(columns={'ifname': 'direct If'})
        return df

    def _augment_evpnvni_show(self, df):
        if not df.empty:
            df = df.explode('remoteVtepList').dropna(how='any')
            df = df.rename(columns={'remoteVtepList': 'peerIP'})
            df = df.merge(self.ip_table, on=['namespace', 'peerIP'],
                          how='left').dropna(how='any').drop_duplicates()
        return df

    def _augment_arpnd_show(self, df):

        if not df.empty:
            # address are where I find the neighbor, these own the mac
            addr = self.address_df[['namespace', 'hostname', 'macaddr']] \
                .drop_duplicates() \
                .rename(columns={'hostname': 'peerHostname'})
            df = df.merge(addr, on=['namespace', 'macaddr'], how='left').dropna(how='any') \
                .rename(columns={'oif': 'ifname'}) \
                .drop_duplicates()

            # these are the macs we that are learned via EVPN so we don't want
            evpn_macs = macs.MacsObj(context=self.ctxt).get(namespace=self._namespaces) \
                .query('remoteVtepIp != ""')[['namespace', 'hostname', 'macaddr']]
            df = df.merge(evpn_macs, on=['namespace', 'hostname', 'macaddr'], how='outer', indicator=True) \
                   .query('_merge=="left_only"') \
                   .drop(columns=['_merge'])

        self._arpnd_df = df
        return self._arpnd_df

    @property
    def address_df(self):
        if self._a_df.empty:
            self._a_df = address.AddressObj(
                context=self.ctxt).get(namespace=self._namespaces)
        return self._a_df

    @property
    def ip_table(self):
        if self._ip_table.empty:
            addr = self.address_df
            if not addr.empty:
                self._ip_table = addr[['namespace',
                                       'hostname', 'ipAddressList']]
                self._ip_table = self._ip_table.explode(
                    'ipAddressList').dropna(how='any')
                self._ip_table = self._ip_table.rename(columns={'ipAddressList': 'peerIP',
                                                                'hostname': 'peerHostname'})
                self._ip_table['peerIP'] = self._ip_table['peerIP'].str.replace(
                    "/.+", "")
                self._ip_table = self._ip_table[self._ip_table['peerIP'] != '-']
        return self._ip_table

    def summarize(self, **kwargs):
        self.get(**kwargs)
        self._create_graphs_from_lsdb()
        if self.lsdb.empty:
            return self.lsdb
        self.ns = {}
        for i in self.nses:
            self.ns[i] = {}
        self._analyze_lsdb_graph()
        self._make_images()

        return pd.DataFrame(self.ns)

    def _analyze_lsdb_graph(self):
        for ns in self.nses:
            for name in [srv.name for srv in self.services if
                         nx.get_edge_attributes(self.graphs[ns], srv.name)]:

                G = nx.Graph([(s, d, data) for s, d, data in
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

                    self.ns[ns][f'{name}_self_loops'] = list(
                        nx.nodes_with_selfloops(G))

                    self.ns[ns][f'{name}_number_of_disjoint_sets'] = len(
                        list(nx.connected_components(G)))

                    self.ns[ns][f'{name}_degree_histogram'] = nx.degree_histogram(
                        G)

                    # if there are too many degrees than the column gets too big
                    if len(self.ns[ns][f'{name}_degree_histogram']) > 6:
                        self.ns[ns][f'{name}_degree_histogram'] = '...'

                else:
                    for k in [f'{name}_is_fully_connected', f'{name}_center',
                              f'{name}_self_loops', f'{name}_number_of_disjoint_sets',
                              f'{name}_degree_histogram', f'{name}_number_of_nodes',
                              f'{name}_number_of_edges']:
                        self.ns[ns][k] = None

    def _make_images(self):
        if not os.path.exists(graph_output_dir):
            os.makedirs(graph_output_dir)
        for ns in self.nses:
            pos = nx.spring_layout(self.graphs[ns])
            for name in [srv.name for srv in self.services if
                         nx.get_edge_attributes(self.graphs[ns], srv.name)]:
                edges = [(u, v) for u, v, d in self.graphs[ns].edges(data=True) if
                         d[name] == True]
                if len(edges) > 1:

                    nx.draw_networkx_nodes(
                        self.graphs[ns], pos=pos, node_size=25)
                    if len(self.graphs[ns].nodes) < 20:
                        nx.draw_networkx_labels(
                            self.graphs[ns], pos=pos, font_size=8)

                    nx.draw_networkx_edges(
                        self.graphs[ns], edgelist=edges, pos=pos)
                    plt.savefig(f"{graph_output_dir}/{ns}_{name}.png")
                    print(f"created {graph_output_dir}/{ns}_{name}.png")
                    plt.close()


@dataclass(frozen=True)
class Services:
    name: str
    data: SqObject
    extra_args: dict
    extra_cols: list
    augment: any
