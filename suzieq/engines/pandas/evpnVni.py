import numpy as np
import pandas as pd
import ipaddress

from .engineobj import SqEngineObject
from suzieq.sqobjects.macs import MacsObj
from suzieq.sqobjects.interfaces import IfObj
from suzieq.sqobjects.routes import RoutesObj


class EvpnvniObj(SqEngineObject):

    def get(self, **kwargs) -> pd.DataFrame:
        """Class-specific to extract info from addnl tables"""

        drop_cols = []
        addnl_fields = kwargs.pop('addnl_fields', [])
        columns = kwargs.get('columns', [])
        if 'ifname' not in columns and 'ifname' not in addnl_fields:
            addnl_fields.append('ifname')
            drop_cols.append('ifname')

        if (columns == ['default'] or columns == ['*'] or
                'remoteVtepCnt' in columns):
            getVtepCnt = True
            if columns != ['*'] and 'remoteVtepList' not in columns:
                addnl_fields.append('remoteVtepList')
                drop_cols.append('remoteVtepList')
        else:
            getVtepCnt = False

        df = super().get(addnl_fields=addnl_fields, **kwargs)
        if df.empty:
            return df

        if getVtepCnt:
            df.insert(len(df.columns)-4, 'remoteVtepCnt',
                      df.remoteVtepList.str.len())

        # See if we can retrieve the info to fill out the rest of the data
        # Start with VLAN values
        if 'vlan' not in df.columns:
            return df.drop(columns=drop_cols, errors='ignore')

        iflist = df[df.vlan == 0]['ifname'].to_list()
        if iflist:
            ifdf = IfObj(context=self.ctxt).get(
                namespace=kwargs.get('namespace', []), ifname=iflist,
                columns=['namespace', 'hostname', 'ifname', 'state', 'vlan',
                         'vni'])

            if not ifdf.empty:
                df = df.merge(ifdf, on=['namespace', 'hostname', 'ifname',
                                        'vni'], how='left',
                              suffixes=('', '_y')) \
                    .drop(columns=['timestamp_y', 'state_y'])

                df['vlan'] = np.where(df['vlan_y'], df['vlan_y'], df['vlan'])
                df.drop(columns=['vlan_y'], inplace=True)

        # Fill out the numMacs and numArps columns if we can
        if 'numMacs' in df.columns:
            vlanlist = list(set(df[df.numMacs == 0]['vlan'].to_list()))
        else:
            vlanlist = []
        if vlanlist:
            if 'numMacs' in df.columns:
                macdf = MacsObj(context=self.ctxt).get(
                    namespace=kwargs.get('namespace'))
                df['numMacs'] = df.apply(self._count_macs, axis=1,
                                         args=(macdf, ))
        return df.drop(columns=drop_cols, errors='ignore')

    def _count_macs(self, x, df):
        return df[(df.namespace == x['namespace']) & (df.vlan == x['vlan']) &
                  (df.hostname == x['hostname'])].count()

    def summarize(self, **kwargs):
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('uniqueVtepCnt', 'hostname', 'nunique'),
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
            ('uniqueMulticastGroups', 'mcastGroup != "0.0.0.0"', 'mcastGroup',
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

        assert_cols = ["namespace", "hostname", "vni", "remoteVtepList", "vrf",
                       "mcastGroup", "type", "priVtepIp", "state", "l2VniList",
                       "ifname", "secVtepIp"]

        kwargs.pop("columns", None)  # Loose whatever's passed
        status = kwargs.pop('status', 'all')

        df = self.get(columns=assert_cols, **kwargs)
        if df.empty:
            df = pd.DataFrame(columns=assert_cols)
            if status != 'pass':
                df['assertReason'] = 'No data found'
                df['assert'] = 'fail'
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

        if (not her_df.empty and
                (her_df.remoteVtepList.str.len() != 0).any()):
            # Check if every VTEP we know is reachable
            rdf = RoutesObj(context=self.ctxt).get(
                namespace=kwargs.get('namespace'), vrf='default')
            if not rdf.empty:
                rdf['prefixlen'] = rdf['prefix'].str.split('/') \
                                                    .str[1].astype('int')
            self._routes_df = rdf

            her_df["assertReason"] += her_df.apply(
                self._is_vtep_reachable, axis=1)

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
        ifdf = IfObj(context=self.ctxt) \
            .get(namespace=kwargs.get("namespace", ""), hostname=devices,
                 type='vxlan')

        df = df.merge(ifdf[['namespace', 'hostname', 'ifname', 'master',
                            'vlan']],
                      on=['namespace', 'hostname', 'ifname'], how='left')

        # vxlan interfaces, if defined, for every VNI is part of bridge
        # We ensure this is true artificially for NXOS, ignored for JunOS.
        df["assertReason"] += df.apply(
            lambda x: ['vni not in bridge']
            if (x['type'] == "L2" and x['ifname'] != '-'
                and x['master'] != "bridge") else [],
            axis=1)

        # mac_df = MacsObj(context=self.ctxt) \
        #     .get(namespace=kwargs.get("namespace", ""),
        #          macaddr=["00:00:00:00:00:00"])

        # # Assert that we have HER for every remote VTEP
        # df['assertReason'] += df.apply(self._is_her_good,
        #                                args=(mac_df, ), axis=1)

        # Fill out the assert column
        df['assert'] = df.apply(lambda x: 'pass'
                                if not len(x.assertReason) else 'fail',
                                axis=1)

        if status == 'fail':
            df = df.query('assertReason.str.len() != 0')
        elif status == "pass":
            df = df.query('assertReason.str.len() == 0')

        return df[['namespace', 'hostname', 'vni', 'type',
                   'assertReason', 'assert', 'timestamp']] \
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

        return (['some remote VTEPs missing'])

    def _is_vtep_reachable(self, row):
        reason = []
        defrt = ipaddress.IPv4Network("0.0.0.0/0")
        for vtep in row['remoteVtepList'].tolist():
            if vtep == '-':
                continue

            # Have to hardcode lpm query here sadly to avoid reading of the
            # data repeatedly. The time for asserting the state of 500 VNIs
            # came down from 194s to 4s with the below piece of code instead
            # of invoking route's lpm to accomplish the task.
            cached_df = self._routes_df \
                            .query(f'namespace=="{row.namespace}" and hostname=="{row.hostname}"')
            route = RoutesObj(context=self.ctxt).lpm(vrf='default',
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
