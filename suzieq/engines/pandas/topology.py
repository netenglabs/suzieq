from dataclasses import dataclass

import networkx as nx
import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.shared.utils import build_query_str

# TODO:
# topology for different VRFs?
# iBGP vs eBGP?
# color by device type?
# physical topology without LLDP -- is this possible?
# how to draw multiple topologies
# be able to ask if a node has neighbors by type (physical, overlay, protocol,
# etc) questions
# * without knowing hierarchy, labels or tags it's unclear how to group things
#   for good picture
# how could we add state of connection (like Established) per protocol


class TopologyObj(SqPandasEngine):
    '''Backend class to operate on virtual table, topology, with pandas'''

    def __init__(self, baseobj):
        super().__init__(baseobj)
        self.lsdb = pd.DataFrame()
        self._a_df = pd.DataFrame()
        self._ip_table = pd.DataFrame()
        self.nses = []

    @staticmethod
    def table_name():
        '''Table name'''
        return 'topology'

    # pylint: disable=attribute-defined-outside-init
    def _init_dfs(self, namespaces):
        """Initialize the dataframes used for the given namespace"""

        self._if_df = self._get_table_sqobj('interfaces') \
            .get(namespace=namespaces, state="up",
                 columns=['namespace', 'hostname', 'ifname', 'ipAddressList',
                          'ip6AddressList', 'state', 'type', 'master',
                          'macaddr'])

        if self._if_df.empty:
            return

        self._if_df['vrf'] = self._if_df.apply(
            lambda x: x['master'] if x['type'] not in ['bridge', 'bond_slave']
            else 'default', axis=1)
        self._if_df['vrf'] = np.where(self._if_df['vrf'] == '', 'default',
                                      self._if_df['vrf'])
        self._if_df = self._if_df.explode('ipAddressList') \
                                 .explode('ip6AddressList') \
                                 .fillna({'ipAddressList': '0.0.0.0/0',
                                          'ip6AddressList': '::0/0'})
        self._if_df['plen'] = self._if_df.ipAddressList.str.split('/').str[1]
        self._if_df['ipAddress'] = self._if_df.ipAddressList.str.split(
            '/').str[0]
        self._if_df = self._if_df.drop(
            columns=['ipAddressList', 'ip6AddressList'])

        self.nses = self._if_df['namespace'].unique()

    # pylint: disable=too-many-statements
    def get(self, **kwargs):
        '''DIsplay the topology info'''

        @dataclass(frozen=True)
        class Services:
            '''minor class for use below. Could have been a named tuple'''
            name: str
            extra_args: dict
            extra_cols: list
            augment: any

        self._namespaces = kwargs.get("namespace", self.ctxt.namespace)
        hostname = kwargs.pop('hostname', [])
        user_query = kwargs.pop('query_str', '')
        polled = kwargs.pop('polled', '')
        via = kwargs.pop('via', [])
        ifname = kwargs.pop('ifname', '')
        peerHostname = kwargs.pop('peerHostname', [])
        columns = kwargs.pop('columns', ['default'])
        asn = kwargs.pop('asn', '')
        area = kwargs.pop('area', '')
        vrf = kwargs.pop('vrf', '')
        afi_safi = kwargs.pop('afiSafi', '')

        self._init_dfs(self._namespaces)
        if self._if_df.empty:
            return pd.DataFrame({'error': ['No interfaces data found']})

        fields = self.schema.get_display_fields(columns)

        if (asn or afi_safi) and area:
            raise AttributeError(
                'Cannot provide asn/afiSafi and area at the same time')

        if any(x in columns for x in ['asn', 'afiSafi']) or asn or afi_safi:
            # When you don't constrain the via to bgp when asn is explicitly
            # requested, we can have some issues. unique or any sort of sorting
            # on the asn column will fail because all rows without BGP == true
            # will have asn as either an undefined value, 0 or blank. The net
            # result of this will be to confuse the user. Think of all the pain
            # automation scripts will have to endure for this.
            if via and via != ['bgp']:
                raise AttributeError(
                    'Cannot provide any via except bgp with asn')
            via = ['bgp']

        if area or 'area' in columns:
            if via and via != ['ospf']:
                raise AttributeError(
                    'Cannot provide any via except ospf with area')
            via = ['ospf']

        if not via:
            via = ['lldp', 'bgp', 'ospf']

        self.services = [
            Services('lldp', {}, ['ifname', 'vrf'],
                     self._augment_lldp_show),
            Services('arpnd', {},
                     ['ipAddress', 'macaddr', 'ifname', 'vrf', 'arpndBidir'],
                     self._augment_arpnd_show),
            Services('bgp', {'state': 'Established', 'asn': asn,
                             'afiSafi': afi_safi, 'vrf': vrf,
                             'columns': ['*']},
                     ['vrf', 'asn', 'peerAsn'],
                     self._augment_bgp_show),
            # Services('evpnVni', {}, 'peerHostname',
            #    'vni', self._augment_evpnvni_show),
            Services('ospf', {'state': 'full', 'area': area, 'vrf': vrf},
                     ['ifname', 'vrf', 'area'], self._augment_ospf_show),
        ]

        if via:
            self.services = [x for x in self.services if x.name in via]
        key = 'peerHostname'

        for srv in self.services:
            if 'columns' not in srv.extra_args:
                srv.extra_args['columns'] = ['default']
            extra_cols = list(srv.extra_cols)
            df = self._get_table_sqobj(srv.name).get(
                **kwargs,
                **srv.extra_args
            )
            if not df.empty:
                if srv.augment:
                    df = srv.augment(df)
                cols = ['namespace', 'hostname', key]
                if extra_cols:
                    cols = cols + extra_cols
                df = df[cols]
                df.insert(len(df.columns), srv.name, True)
                if self.lsdb.empty:
                    self.lsdb = df
                else:
                    self.lsdb = self.lsdb.merge(df, how='outer')
            else:
                self.lsdb[srv.name] = False

        self.lsdb = self.lsdb.fillna('').reset_index(drop=True)
        self._find_polled_neighbors(polled)
        if self.lsdb.empty:
            return self.lsdb

        if 'ipAddress' not in self.lsdb.columns:
            self.lsdb['ipAddress'] = ''

        self.lsdb = self.lsdb[~self.lsdb.hostname.isna()] \
                        .drop_duplicates() \
                        .rename({'ipAddress': 'peerIP', 'macaddr': 'peerMac'},
                                axis=1, errors='ignore') \
                        .dropna(subset=['peerHostname', 'peerIP'], how='all') \
                        .fillna({'peerHostname': 'unknown',
                                 'ifname': 'unknown', 'arpnd': False,
                                 'peerIP': '', 'peerMac': '',
                                 'arpndBidir': False,
                                 'bgp': False, 'ospf': False,
                                 'lldp': False, 'vrf': 'N/A'})

        self.lsdb['vrf'] = np.where(self.lsdb.vrf == "bridge", "-",
                                    self.lsdb.vrf)
        self.lsdb['peerHostname'] = np.where(
            self.lsdb.peerHostname == "unknown", self.lsdb.peerIP,
            self.lsdb.peerHostname)
        self.lsdb = self.lsdb.drop(columns=['peerIP', 'peerMac'],
                                   errors='ignore')
        self.lsdb = self.lsdb.query('peerHostname != ""')

        # Apply the appropriate filters
        if not self.lsdb.empty:
            self.lsdb = self.lsdb.fillna('')
            query_str = build_query_str([], self.schema, ignore_regex=False,
                                        hostname=hostname,
                                        peerHostname=peerHostname,
                                        ifname=ifname, asn=asn, area=area,
                                        vrf=vrf)
            if query_str:
                self.lsdb = self.lsdb.query(query_str)

        if user_query and not self.lsdb.empty:
            self.lsdb = self._handle_user_query_str(self.lsdb, user_query)

        fields = [x for x in fields if x in self.lsdb.columns]
        return self.lsdb[fields].reset_index(drop=True)

    def _find_polled_neighbors(self, polled):
        if self.lsdb.empty:
            return

        hosts = set(self.lsdb.hostname)
        peer_hosts = set(self.lsdb.peerHostname)
        unpolled_neighbors = peer_hosts.difference(hosts)

        self.lsdb['polled'] = True
        self.lsdb.loc[self.lsdb.peerHostname.isin(unpolled_neighbors),
                      'polled'] = False

        if polled and polled.lower() == 'true':
            self.lsdb = self.lsdb.query('polled')
        elif polled.lower() == 'false':
            self.lsdb = self.lsdb.query('~polled')

    def _create_graphs_from_lsdb(self):
        self.graphs = {}
        for ns, df in self.lsdb.groupby(by=['namespace']):
            attrs = [srv.name for srv in self.services
                     if srv.name in df.columns]
            self.graphs[ns] = nx.from_pandas_edgelist(
                df, 'hostname', 'peerHostname', attrs, nx.MultiGraph)

    # TODO: eventually this needs to move to ospf after we figure out the
    #   schema augmentation story
    def _augment_ospf_show(self, df):
        if not df.empty:
            df = df.query('adjState != "passive"').reset_index(drop=True)
            df['area'] = df['area'].astype(str)
        return df

    def _augment_lldp_show(self, df):
        if not df.empty and not self._if_df.empty:
            df = df[df.peerHostname != '']
            df = df.merge(
                self._if_df[['namespace', 'hostname', 'ifname', 'vrf']],
                on=['namespace', 'hostname', 'ifname'], how='outer')

        return df

    def _augment_bgp_show(self, df):
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
            # weed out entries that are not reachable
            df = df.query('state != "failed"').reset_index(drop=True)
            # Get the VRF
            df = df.merge(
                self._if_df[['namespace', 'hostname', 'ifname', 'master']],
                left_on=['namespace', 'hostname', 'oif'],
                right_on=['namespace', 'hostname', 'ifname'],
                suffixes=['', '_y'], how='outer') \
                .rename(columns={'master': 'vrf'}) \
                .dropna(subset=['ipAddress'])

            df['vrf'] = np.where(df['vrf'] == '', 'default', df['vrf'])
            df = df.drop(columns=['vlan', 'oif', 'mackey', 'remoteVtepIp',
                                  'timestamp_y'], errors='ignore')

            # address are where I find the neighbor, these own the mac
            addr = self.address_df[['namespace', 'hostname', 'macaddr']] \
                .drop_duplicates() \
                .rename(columns={'hostname': 'peerHostname'})
            df = df.merge(addr, on=['namespace', 'macaddr'], how='left') \
                   .dropna(subset=['hostname', 'ipAddress']) \
                   .rename(columns={'oif': 'ifname'}) \
                   .drop_duplicates()

            # Use MAC table entries to find the local port for a MAC on an SVI
            mac_df = self._get_table_sqobj('macs')\
                         .get(namespace=self._namespaces, local=True,
                              columns=['namespace', 'hostname', 'vlan',
                                       'macaddr', 'oif', 'remoteVtepIp'])
            df = df.merge(mac_df,
                          on=['namespace', 'hostname', 'macaddr'],
                          how='outer') \
                .dropna(subset=['hostname'])
            df['ifname'] = np.where(
                df['oif'].isnull(), df['ifname'], df['oif'])

            df['arpndBidir'] = df.apply(
                lambda x, y:
                not y.query(f'namespace=="{x.namespace}" and '
                            f'hostname=="{x.peerHostname}" and '
                            f'peerHostname=="{x.hostname}"').empty,
                args=(df,), axis=1)

        self._arpnd_df = df
        return self._arpnd_df

    @property
    def address_df(self) -> pd.DataFrame():
        '''Return pandas dataframe of the address table'''

        if self._a_df.empty:
            self._a_df = self._if_df
        return self._a_df

    @property
    def ip_table(self):
        '''Return a dataframe of '''
        if self._ip_table.empty:
            addr = self.address_df
            if not addr.empty:
                self._ip_table = addr[['namespace',
                                       'hostname', 'ipAddressList']]
                self._ip_table = self._ip_table.explode(
                    'ipAddressList').dropna(how='any')
                self._ip_table = self._ip_table \
                                     .rename(
                                         columns={'ipAddressList': 'peerIP',
                                                  'hostname': 'peerHostname'})
                self._ip_table['peerIP'] = self._ip_table['peerIP'] \
                                               .str.replace("/.+", "")
                self._ip_table = \
                    self._ip_table[self._ip_table['peerIP'] != '-']
        return self._ip_table

    def summarize(self, **kwargs):
        '''Summarize the topology info'''
        self.get(**kwargs)
        if self.lsdb.empty:
            return self.lsdb

        self.ns = {}
        for i in self.nses:
            self.ns[i] = {}
        self._create_graphs_from_lsdb()
        self._analyze_lsdb_graph()

        return pd.DataFrame(self.ns)

    def _analyze_lsdb_graph(self):
        for ns in self.nses:
            for name in [srv.name for srv in self.services if
                         nx.get_edge_attributes(self.graphs[ns], srv.name)]:

                G = nx.Graph([(s, d, data) for s, d, data in
                              self.graphs[ns].edges(data=True)
                              if data[name] is True])
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

                    self.ns[ns][f'{name}_degree_histogram'] = \
                        nx.degree_histogram(G)

                    # too many degrees => the column gets too big
                    if len(self.ns[ns][f'{name}_degree_histogram']) > 6:
                        self.ns[ns][f'{name}_degree_histogram'] = '...'

                else:
                    for k in [f'{name}_is_fully_connected', f'{name}_center',
                              f'{name}_self_loops',
                              f'{name}_number_of_disjoint_sets',
                              f'{name}_degree_histogram',
                              f'{name}_number_of_nodes',
                              f'{name}_number_of_edges']:
                        self.ns[ns][k] = None
