import ipaddress

import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class EvpnvniObj(SqPandasEngine):
    '''Backend class to handle manipulating evpnVni table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'evpnVni'

    def get(self, **kwargs) -> pd.DataFrame:
        """Class-specific to extract info from addnl tables"""

        columns = kwargs.pop('columns', [])
        query_str = kwargs.pop('query_str', [])

        addnl_fields = []
        fields = self.schema.get_display_fields(columns)
        if 'ifname' not in fields+addnl_fields:
            addnl_fields.append('ifname')

        if 'remoteVtepCnt' in fields:
            getVtepCnt = True
            if 'remoteVtepList' not in fields:
                addnl_fields.append('remoteVtepList')
        else:
            getVtepCnt = False

        user_query_cols = self._get_user_query_cols(query_str)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        df = super().get(addnl_fields=addnl_fields, columns=fields, **kwargs)
        if df.empty:
            return df

        if getVtepCnt:
            insidx = df.columns.tolist().index('remoteVtepList')
            df.insert(insidx+1, 'remoteVtepCnt',
                      df.remoteVtepList.str.len())

        # See if we can retrieve the info to fill out the rest of the data
        # Start with VLAN values
        if 'vlan' not in df.columns and 'vrf' not in df.columns:
            return df.reset_index(drop=True)[fields]

        iflist = [x for x in df[df.vlan == 0]['ifname'].to_list()
                  if x and x != 'None']
        if iflist:
            ifdf = self._get_table_sqobj('interfaces').get(
                namespace=kwargs.get('namespace', []), ifname=iflist,
                columns=['namespace', 'hostname', 'ifname', 'state', 'vlan',
                         'vni'])

            if not ifdf.empty:
                df = df.merge(ifdf, on=['namespace', 'hostname', 'ifname'],
                              how='left', suffixes=('', '_y')) \
                    .drop(columns=['timestamp_y', 'state_y', 'vni_y'],
                          errors='ignore')

                df['vlan'] = np.where(
                    df['vlan_y'].notnull(), df['vlan_y'], df['vlan'])
                df = df.drop(columns=['vlan_y']) \
                       .fillna({'vlan': 0}) \
                       .astype({'vlan': int})

        # Now we try to see if we can get the VRF info for all L2 VNIs as well
        ifdf = self._get_table_sqobj('interfaces') \
            .get(namespace=kwargs.get('namespace', []), type=['vlan'],
                 columns=['namespace', 'hostname', 'vlan', 'master']) \
            .query('master != ""') \
            .reset_index(drop=True)
        if not ifdf.empty and not df.empty and 'vrf' in df.columns:
            df = df.merge(ifdf, left_on=['namespace', 'hostname', 'vlan'],
                          right_on=['namespace', 'hostname', 'vlan'],
                          how='outer', suffixes=('', '_y'))

            # We fix the VRF from L2 VNIs from the SVI interface's master info
            # and we drop those entries that are just local VLANs, without VNI
            df['vrf'] = np.where(df['vrf'] == "", df['master'], df['vrf'])
            df = df.drop(columns=['master', 'timestamp_y'], errors='ignore') \
                   .dropna(subset=['vni'])

        # Fill out the numMacs and numArps columns if we can
        if 'numMacs' in df.columns:
            vlanlist = list(set(df[df.numMacs == 0]['vlan'].to_list()))
        else:
            vlanlist = []
        if vlanlist:
            if 'numMacs' in df.columns:
                macdf = self._get_table_sqobj('macs').get(
                    namespace=kwargs.get('namespace'))
                if not macdf.empty:
                    mac_count_df = macdf \
                        .query('flags.isin(["dynamic", "remote"])') \
                        .groupby(['namespace', 'hostname', 'vlan']) \
                        .macaddr.count().reset_index()
                    df = df.merge(mac_count_df,
                                  on=['namespace', 'hostname', 'vlan'],
                                  suffixes=['', '_y'], how='left') \
                        .drop(columns=['numMacs'], errors='ignore') \
                        .rename(columns={'macaddr': 'numMacs'}) \
                        .fillna({'numMacs': 0})

        for x in ['vlan', 'vni']:
            if x in df.columns:
                df[x] = np.where(df[x].isnull(), 0,
                                 df[x].astype(int))

        df = self._handle_user_query_str(df, query_str)
        return df.reset_index(drop=True)[fields]

    def _count_macs(self, x, df):
        return df[(df.namespace == x['namespace']) & (df.vlan == x['vlan']) &
                  (df.hostname == x['hostname'])].count()

    def summarize(self, **kwargs):
        self._init_summarize(**kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('uniqueVtepCnt', 'priVtepIp', 'nunique'),
            ('uniqueVniCnt', 'vni', 'nunique'),
        ]

        l3vni_count = self.summary_df.query('type == "L3" and vni != 0') \
            .groupby(by=['namespace'])['vni'].count()
        for ns in self.ns.keys():
            if l3vni_count.get(ns, 0):
                self.ns[ns]['mode'] = 'symmetric'
            else:
                self.ns[ns]['mode'] = 'asymmetric'
        self.summary_row_order.append('mode')

        self._summarize_on_add_with_query = [
            ('uniqueL3VniCnt', 'type == "L3" and vni != 0', 'vrf', 'nunique'),
            ('uniqueL2VniCnt', 'type == "L2"', 'vni', 'nunique'),
            ('uniqueMulticastGroups',
             'mcastGroup != "0.0.0.0" and mcastGroup != ""', 'mcastGroup',
             'nunique'),
            ('vnisUsingMulticast',
             'type == "L2" and replicationType == "multicast"',
             'vni', 'nunique'),
            ('vnisUsingIngressRepl',
             'type == "L2" and replicationType == "ingressBGP"',
             'vni', 'nunique')
        ]

        self._gen_summarize_data()

        # To summarize accurately, we need to explode the remoteVteps
        # column from a list to an individual entry for each
        # remoteVteps in that list. The resulting set can be huge if them
        # number of Vteps times the ports is huge.
        #
        # the 'explode' only works post pandas 0.25

        self.summary_df = self.summary_df.explode(
            'remoteVtepList').dropna(how='any')
        self.nsgrp = self.summary_df.groupby(by=["namespace"])

        if not self.summary_df.empty:
            herPerVtepCnt = self.summary_df.groupby(
                by=['namespace', 'hostname'])['remoteVtepList'].nunique()
            self._add_stats_to_summary(herPerVtepCnt, 'remoteVtepsPerVtepStat',
                                       filter_by_ns=True)
        self.summary_row_order.append('remoteVtepsPerVtepStat')

        self._post_summarize(check_empty_col='uniqueVtepCnt')
        return self.ns_df.convert_dtypes()

    def aver(self, **kwargs) -> pd.DataFrame:
        """Assert for EVPN Data"""

        assert_cols = ["namespace", "hostname", "vni", "vlan",
                       "remoteVtepList", "vrf", "mcastGroup", "type",
                       "priVtepIp", "state", "l2VniList", "ifname",
                       "secVtepIp", "timestamp"]

        kwargs.pop("columns", None)  # Loose whatever's passed
        result = kwargs.pop('result', 'all')

        df = self.get(columns=assert_cols, **kwargs)
        if df.empty:
            df = pd.DataFrame(columns=assert_cols)
            if result != 'pass':
                df['assertReason'] = 'No data found'
                df['result'] = 'fail'
            return df

        df["assertReason"] = [[] for _ in range(len(df))]

        # Gather the unique set of VTEPs per VNI
        vteps_df = df.explode(column='remoteVtepList') \
            .dropna(how='any') \
            .groupby(by=['vni', 'type'])['remoteVtepList'] \
            .aggregate(lambda x: x.unique().tolist()) \
            .reset_index() \
            .dropna(how='any') \
            .rename(columns={'remoteVtepList': 'allVteps'})

        if not vteps_df.empty:
            her_df = df.merge(vteps_df)
        else:
            her_df = pd.DataFrame()

        # if (not her_df.empty and
        #         (her_df.remoteVtepList.str.len() != 0).any()):
        #     # Check if every VTEP we know is reachable
        #     rdf = self._get_table_sqobj('routes').get(
        #         namespace=kwargs.get('namespace'), vrf='default')
        #     if not rdf.empty:
        #         rdf['prefixlen'] = rdf['prefix'].str.split('/') \
        #                                             .str[1].astype('int')
        #     her_df["assertReason"] += her_df.apply(
        #         self._is_vtep_reachable, args=(rdf,), axis=1)

        mcast_df = df.query('mcastGroup != "0.0.0.0"')
        if not mcast_df.empty:
            # Ensure that all VNIs have at most one multicast group associated
            # per namespace

            mismatched_vni_df = mcast_df \
                .groupby(by=['namespace', 'vni'])['mcastGroup'] \
                .unique() \
                .reset_index() \
                .dropna() \
                .query('mcastGroup.str.len() != 1')

            if not mismatched_vni_df.empty:
                df['assertReason'] += df.apply(
                    lambda x, err_df: ['VNI has multiple mcast group']
                    if (x['namespace'] in err_df['namespace'] and
                        x['vni'] in err_df['vni']) else [], axis=1,
                    args=(mismatched_vni_df, ))
        elif not her_df.empty:
            # Every VTEP has info about every other VTEP for a given VNI
            her_df["assertReason"] += her_df.apply(
                self._all_vteps_present, axis=1)

        # State is up
        df["assertReason"] += df.apply(
            lambda x: ['interface is down']
            if x['type'] == "L2" and x['state'] != "up"
            else [], axis=1)

        devices = df["hostname"].unique().tolist()
        ifdf = self._get_table_sqobj('interfaces') \
            .get(namespace=kwargs.get("namespace", ""), hostname=devices,
                 type='vxlan')

        df = df.merge(ifdf[['namespace', 'hostname', 'ifname', 'master',
                            'vlan']],
                      on=['namespace', 'hostname', 'ifname'], how='left')

        # vxlan interfaces, if defined, for every VNI is part of bridge
        # We ensure this is true artificially for NXOS, ignored for JunOS.
        df["assertReason"] += df.apply(
            lambda x: ['vni not in bridge']
            if (x['type'] == "L2" and x['ifname'] != ''
                and x['master'] != "bridge") else [],
            axis=1)

        mac_df = self._get_table_sqobj('macs') \
            .get(namespace=kwargs.get("namespace", ""),
                 macaddr=["00:00:00:00:00:00"], remoteVtepIp=['any'])

        # # Assert that we have HER for every remote VTEP; Cumulus/SONiC
        if not mac_df.empty:
            df['assertReason'] += df.apply(self._is_her_good,
                                           args=(mac_df, ), axis=1)

        # Fill out the assert column
        df['result'] = df.apply(lambda x: 'pass'
                                if len(x.assertReason) == 0 else 'fail',
                                axis=1)

        # Force VNI to be an int
        df['vni'] = np.where(df.vni.isnull(), 0,
                             df.vni.astype(int))

        if result == 'fail':
            df = df.query('assertReason.str.len() != 0')
        elif result == "pass":
            df = df.query('assertReason.str.len() == 0')

        return df[['namespace', 'hostname', 'vni', 'type',
                   'assertReason', 'result', 'timestamp']] \
            .explode(column='assertReason') \
            .fillna({'assertReason': '-'})

    def _all_vteps_present(self, row):
        if row['secVtepIp'] == '0.0.0.0':
            myvteps = set([row['priVtepIp']])
        else:
            myvteps = set([row['secVtepIp'], row['priVtepIp']])

        isitme = set(row['allVteps']).difference(set(row['remoteVtepList']))
        if (isitme.intersection(myvteps) or
                (row['type'] == "L3" and row['remoteVtepList'] == ["-"])):
            return []

        return ['some remote VTEPs missing']

    def _is_vtep_reachable(self, row, rdf):
        reason = []
        defrt = ipaddress.IPv4Network("0.0.0.0/0")
        for vtep in row['remoteVtepList'].tolist():
            if vtep == '-':
                continue

            # Have to hardcode lpm query here sadly to avoid reading of the
            # data repeatedly. The time for asserting the state of 500 VNIs
            # came down from 194s to 4s with the below piece of code instead
            # of invoking route's lpm to accomplish the task.
            cached_df = rdf \
                .query(f'namespace=="{row.namespace}" and '
                       f'hostname=="{row.hostname}"')
            route = self._get_table_sqobj('routes').lpm(vrf='default',
                                                        address=vtep,
                                                        cached_df=cached_df)

            if route.empty:
                reason += [f"{vtep} not reachable"]
                continue
            if route.prefix.tolist() == [defrt]:
                reason += [f"{vtep} reachable via default"]

        return reason

    def _is_her_good(self, row, mac_df):
        reason = []

        if row['type'] == 'L3':
            return reason

        her_list = mac_df[(mac_df['hostname'] == row['hostname']) &
                          (mac_df['namespace'] == row['namespace']) &
                          (mac_df['oif'] == row['ifname'])]['remoteVtepIp'] \
            .tolist()
        missing_hers = set(row['remoteVtepList']).difference(set(her_list))
        if not missing_hers:
            return reason
        return [f'HER is missing VTEPs {missing_hers}']
