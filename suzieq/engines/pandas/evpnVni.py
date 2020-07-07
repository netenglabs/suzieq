import pandas as pd
import ipaddress

from .engineobj import SqEngineObject
from suzieq.sqobjects.macs import MacsObj
from suzieq.sqobjects.interfaces import IfObj
from suzieq.sqobjects.routes import RoutesObj


class EvpnvniObj(SqEngineObject):

    def summarize(self, **kwargs):
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('uniqueVniCnt', 'vni', 'nunique'),
        ]

        l3vni_count = self.summary_df.query('type == "L3"').groupby(
            by=['namespace'])['vni'].count()
        for ns in self.ns.keys():
            if l3vni_count[ns]:
                self.ns[ns]['mode'] = 'symmetric'
            else:
                self.ns[ns]['mode'] = 'asymmetric'
        self.summary_row_order.append('mode')

        self._summarize_on_add_with_query = [
            ('uniqueL3VniCnt', 'type == "L3"', 'vrf', 'nunique'),
            ('uniqueL2VniCnt', 'type == "L2"', 'vni', 'nunique'),
        ]

        self._summarize_on_add_list_or_count = [
            ('uniqueVniTypeValCnt', 'type'),
            ('replTypeValCnt', 'replicationType')
        ]

        self._summarize_on_add_stat = [
            ('macsInVniStat', '', 'numMacs'),
            ('arpNdInVniStat', '', 'numArpNd')
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
            self._add_stats_to_summary(herPerVtepCnt, 'ingressReplPerVtepStat',
                                       filter_by_ns=True)
        self.summary_row_order.append('ingressReplPerVtepStat')

        self._post_summarize(check_empty_col='deviceCnt')
        return self.ns_df.convert_dtypes()

    def aver(self, **kwargs) -> pd.DataFrame:
        """Assert for EVPN Data"""

        assert_cols = ["namespace", "hostname", "vni", "remoteVtepList", "vrf",
                       "mcastGroup", "type", "priVtepIp", "state", "l2VniList",
                       "ifname", "secVtepIp"]

        kwargs.pop("columns", None)  # Loose whatever's passed

        df = self.get(columns=assert_cols, **kwargs)
        if df.empty:
            df = pd.DataFrame(columns=assert_cols)
            df['assertReason'] = 'No data found'
            df['assert'] = 'fail'
            return df

        df["assertReason"] = [[] for _ in range(len(df))]

        her_df = df.query('mcastGroup == "0.0.0.0"')
        # When routed multicast is used as underlay, type 3 routes are not
        # advertised and so its not certain that all VTEPs asssociated with
        # a VNI will know about each other till there's an active local host
        # A bad optimization for routing implementations to do, IMO.
        if not her_df.empty:
            # Gather the unique set of VTEPs per VNI
            vteps_df = her_df.explode(column='remoteVtepList') \
                             .dropna(how='any') \
                             .groupby(by=['vni', 'type'])['remoteVtepList'] \
                             .aggregate(lambda x: x.unique().tolist()) \
                             .reset_index() \
                             .dropna(how='any') \
                             .rename(columns={'remoteVtepList': 'allVteps'})

            her_df = her_df.merge(vteps_df)

            # Every VTEP has info about every other VTEP for a given VNI
            her_df["assertReason"] += her_df.apply(
                self._all_vteps_present, axis=1)

            # Every VTEP is reachable
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
            rdf = RoutesObj(context=self.ctxt) \
                .lpm(namespace=row['namespace'], vrf=['default'],
                     hostname=row['hostname'], address=vtep)
            if rdf.empty:
                reason += [f"{vtep} not reachable"]
                continue
            if rdf.prefix[0] == defrt:
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
