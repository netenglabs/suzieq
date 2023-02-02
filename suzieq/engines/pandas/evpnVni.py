import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class EvpnvniObj(SqPandasEngine):
    '''Backend class to handle manipulating evpnVni table with pandas'''

    def __init__(self, baseobj):
        super().__init__(baseobj)
        self._assert_result_cols = ['namespace', 'hostname', 'vni', 'type',
                                    'vrf', 'macaddr', 'timestamp', 'result',
                                    'assertReason']

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
        self._add_active_to_fields(kwargs.get('view', self.iobj.view), fields,
                                   addnl_fields)

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
            ifdf = self._get_table_sqobj('interfaces', start_time='').get(
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

        result = kwargs.pop('result', 'all')
        kwargs.pop('columns', None)

        df = self._init_assert_df(**kwargs)

        res_cols = self._assert_result_cols

        if df.empty:
            df = pd.DataFrame(columns=res_cols)
            if result != 'pass':
                df['assertReason'] = 'No data found'
                df['result'] = 'fail'
            return df[res_cols]

        df["assertReason"] = [[] for _ in range(len(df))]

        df['assertReason'] += df.apply(
            lambda x: ['vni down'] if x['state'] != "up" else [],
            axis=1)

        mcast_df = df.query('mcastGroup != "0.0.0.0"')
        if not mcast_df.empty:
            self._validate_vni_replication(df)
            self._validate_mcast_vni_consistency(df, mcast_df)
        else:
            self._validate_all_vteps_known(df)

        self._validate_vni_vrf_consistency(df)

        self._validate_anycast_mac(df)

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

        return df[res_cols]

    def _init_assert_df(self, **kwargs):
        '''Prepare for running asserts'''

        addnl_cols = kwargs.pop('addnl_cols', [])
        kwargs.pop("columns", None)  # Loose whatever's passed
        req_cols = ['*']
        if addnl_cols:
            req_cols += [ac for ac in addnl_cols if ac not in req_cols]

        df = self.get(columns=req_cols, **kwargs)
        addr_df = self._get_table_sqobj('address').get(
            namespace=kwargs.get('namespace', []),
            hostname=kwargs.get('hostname', []), type=['vlan'],
            columns=['namespace', 'hostname', 'ifname', 'vlan', 'vrf',
                     'macaddr']) \
            .reset_index(drop=True)
        df = df.merge(addr_df,
                      on=['namespace', 'hostname', 'vlan'],
                      how='left') \
            .drop(columns=['vrf_x'], errors='ignore') \
            .rename(columns={'vrf_y': 'vrf'})

        vni_vrf_df = df.groupby(by=['namespace', 'vni'])['vrf'] \
                       .nunique() \
                       .reset_index() \
                       .rename(columns={'vrf': 'vrfCnt'})
        df = df.merge(vni_vrf_df, on=['namespace', 'vni'], how='left')
        return df

    def _validate_vni_replication(self, df):
        '''A VNI MUST the same replication model on all hosts'''
        repl_df = df.groupby(['namespace', 'vni'])['replicationType'] \
                    .nunique() \
                    .reset_index()

        df = df.merge(repl_df, on=['namespace', 'vni'])
        df['assertReason'] += df.replicationType_y.apply(
            lambda x: ['inconsistent replication across hosts']
            if x != 1 else [])
        df = df.drop(columns=['replicationType_y'])

        return df

    def _validate_mcast_vni_consistency(self, df, mcast_df):
        '''All VNIs have at most one multicast group associated'''

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

    def _validate_all_vteps_known(self, df):
        '''Every VTEP MUST about every other VTEP for a given VNI with HER'''
        df['pickVtepIp'] = np.where(df.secVtepIp == "", df.priVtepIp,
                                    df.secVtepIp)
        df['avt'] = df.apply(
            lambda x: np.sort(np.append(x['remoteVtepList'],
                                        [x['pickVtepIp']])),
            axis=1)
        # pylint: disable=unnecessary-lambda
        df['allVteps'] = df.avt.apply(lambda x: ','.join(x))
        known_vteps = df.groupby(by=['namespace', 'vni'])['allVteps'] \
                        .nunique() \
                        .reset_index()
        df = df.merge(known_vteps, on=['namespace', 'vni']) \
               .drop(columns=['avt', 'allVteps_x', 'pickVtepIp']) \
               .rename(columns={'allVteps_y': 'allVtepsCnt'})
        df['assertReason'] += df.allVtepsCnt.apply(
            lambda x: ['Some VTEPs are unknown to all'] if x != 1 else [])

    def _validate_vni_vrf_consistency(self, df):
        '''A L2 VNI MUST be mapped to the same L3VNI on every host'''

        df['assertReason'] += df.vrfCnt.apply(
            lambda x: ['Inconsistent VNI-VRF mapping'] if (x > 1) else [])

    def _validate_anycast_mac(self, df):
        '''All non-L2-only segments MUST have the same anycast MACaddr'''
        rest_df = df.query('type == "L2" and macaddr != "00:00:00:00:00:00"')
        if rest_df.macaddr.nunique() != 1:
            df['assertReason'] += df.vrfCnt.apply(
                lambda x: ['anycast MAC not unique across VNI']
                if x else [])

    def _validate_frr_her(self, df, **kwargs):
        '''In FRR, with ingress replication, look for HER list consistency'''

        mac_df = self._get_table_sqobj('macs') \
            .get(namespace=kwargs.get("namespace", ""),
                 macaddr=["00:00:00:00:00:00"], remoteVtepIp=['any'])

        # # Assert that we have HER for every remote VTEP; Cumulus/SONiC
        if not mac_df.empty:
            df['assertReason'] += df.apply(self._is_her_good,
                                           args=(mac_df, ), axis=1)

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
