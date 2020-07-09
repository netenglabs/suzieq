from suzieq.sqobjects.routes import RoutesObj

import re
import pandas as pd
import numpy as np

from .engineobj import SqEngineObject


class BgpObj(SqEngineObject):

    def get(self, **kwargs):
        """Replacing the original interface name in returned result"""

        addnl_fields = kwargs.pop('addnl_fields', [])
        columns = kwargs.get('columns', ['default'])
        drop_cols = ['origPeer', 'peerHost']

        if columns != ['*']:
            if 'peerIP' not in columns:
                addnl_fields.append('peerIP')
                drop_cols.append('peerIP')
            if 'updateSource' not in columns:
                addnl_fields.append('updateSource')
                drop_cols.append('updateSource')

        addnl_fields.extend(['origPeer'])

        df = super().get(addnl_fields=addnl_fields, **kwargs)

        if df.empty:
            return df

        if 'peer' in df.columns:
            df['peer'] = np.where(df['origPeer'] != "",
                                  df['origPeer'], df['peer'])

        if not all(i in df.columns for i in ['namespace', 'hostname', 'vrf',
                                             'peerIP', 'updateSource']):
            return df.drop(columns=['origPeer'])

        mdf = df.merge(df[['namespace', 'hostname', 'vrf', 'peerIP',
                           'updateSource']],
                       left_on=['namespace', 'vrf', 'peerIP'],
                       right_on=['namespace', 'vrf', 'updateSource'],
                       how='left') \
            .query('peerIP_x == updateSource_y and '
                   'peerIP_y == updateSource_x') \
            .rename(columns={'hostname_y': 'peerHost',
                             'hostname_x': 'hostname',
                             'updateSource_x': 'updateSource',
                             'peerIP_x': 'peerIP'}) \
            .drop(columns=['updateSource_y', 'peerIP_y'])

        mdf['peerHostname'] = mdf['peerHost']
        return mdf.drop(columns=drop_cols)

    def _check_afi_safi(self, row) -> list:
        """Checks that AFI/SAFI is compatible across the peers"""

        reasons = ""
        if not row['peer_y']:
            return []

        if row["v4Enabled_x"] != row["v4Enabled_y"]:
            if row["v4Advertised_x"] and not row["v4Received_x"]:
                reasons += " peer not advertising ipv4/unicast"
            elif row["v4Received_x"] and not row["v4Advertised_x"]:
                reasons += " not advertising ipv4/unicast"
        if row["v6Enabled_x"] != row["v6Enabled_y"]:
            if row["v6Advertised_x"] and not row["v6Received_x"]:
                reasons += " peer not advertising ipv6/unicast"
            elif row["v6Received_x"] and not row["v6Advertised_x"]:
                reasons += " not advertising ipv6/unicast"
        if row["evpnEnabled_x"] != row["evpnEnabled_y"]:
            if row["evpnAdvertised_x"] and not row["evpnReceived_x"]:
                reasons += " peer not advertising evpn"
            elif row["evpnReceived_x"] and not row["evpnAdvertised_x"]:
                reasons += " not advertising evpn"

        if reasons:
            return [reasons]
        return []

    def summarize(self, **kwargs) -> pd.DataFrame:
        """Summarize key information about BGP"""

        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('totalPeerCnt', 'hostname', 'count'),
            ('uniqueAsnCnt', 'peerAsn', 'nunique'),
            ('uniqueVrfsCnt', 'vrf', 'nunique')
        ]

        self._summarize_on_add_with_query = [
            ('failedPeerCnt', 'state == "NotEstd"', 'peer')
        ]

        self._gen_summarize_data()

        self.summary_df['estdTime'] = pd.to_datetime(
            self.summary_df['estdTime'], unit='ms')
        self.summary_df['estdTime'] = (
            self.summary_df['timestamp'] - self.summary_df['estdTime'])
        self.summary_df['estdTime'] = self.summary_df['estdTime'] \
                                          .apply(lambda x: x.round('s'))
        # Now come the BGP specific ones
        established = self.summary_df.query("state == 'Established'") \
            .groupby(by=['namespace'])

        uptime = established["estdTime"]
        v4_updates = established["v4PfxRx"]
        v6_updates = established["v6PfxRx"]
        evpn_updates = established["evpnPfxRx"]
        rx_updates = established["updatesRx"]
        tx_updates = established["updatesTx"]

        self._add_stats_to_summary(uptime, 'upTimeStat')
        self._add_stats_to_summary(v4_updates, 'v4PfxRxStat')
        self._add_stats_to_summary(v6_updates, 'v6PfxRxStat')
        self._add_stats_to_summary(evpn_updates, 'evpnPfxRxStat')
        self._add_stats_to_summary(rx_updates, 'updatesRxStat')
        self._add_stats_to_summary(tx_updates, 'updatesTxStat')

        self.summary_row_order.extend(['upTimeStat', 'v4PfxRxStat',
                                       'v6PfxRxStat', 'evpnPfxRxStat',
                                       'updatesRxStat', 'updatesTxStat'])

        ipv4_enabled = self.summary_df.query("v4Enabled")["namespace"].unique()
        ipv6_enabled = self.summary_df.query("v6Enabled")["namespace"].unique()
        evpn_enabled = self.summary_df.query(
            "evpnEnabled")["namespace"].unique()

        for i in self.ns.keys():
            self.ns[i].update({'activeAfiSafiList': []})
            if i in ipv4_enabled:
                self.ns[i]['activeAfiSafiList'].append("ipv4")
            if i in ipv6_enabled:
                self.ns[i]['activeAfiSafiList'].append("ipv6")
            if i in evpn_enabled:
                self.ns[i]['activeAfiSafiList'].append('evpn')

        self.summary_row_order.append('activeAfiSafiList')
        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def _get_peer_matched_df(self, df) -> pd.DataFrame:
        """Get a BGP dataframe that also contains a session's matching peer"""

        mdf = df.merge(df, left_on=['namespace', 'peerIP'],
                       right_on=['namespace', 'updateSource'], how='left') \
            .query('peerIP_x == updateSource_y and '
                   'peerIP_y == updateSource_x') \
            .rename(columns={'hostname_x': 'hostname', 'vrf_x': 'vrf',
                             'hostname_y': 'peerHostname',
                             'state_x': 'state',
                             'reason_x': 'reason',
                             'timestamp_x': 'timestamp',
                             'vrf_y': 'vrfPeer',
                             'notificnReason_x': 'notificnReason'}) \
            .drop(columns=['state_y', 'reason_y', 'timestamp_y', 'peerIP_x',
                           'peerIP_y'])

        return mdf

    def aver(self, **kwargs) -> pd.DataFrame:
        """BGP Assert"""

        assert_cols = ["namespace", "hostname", "vrf", "peer", "asn", "state",
                       "peerAsn", "v4Enabled", "v6Enabled", "evpnEnabled",
                       "v4Advertised", "v6Advertised", "evpnAdvertised",
                       "v4Received", "v6Received", "evpnReceived", "bfdStatus",
                       "reason", "notifcnReason", "peerIP", "updateSource"]

        kwargs.pop("columns", None)  # Loose whatever's passed

        df = self.get(columns=assert_cols, state='!dynamic', **kwargs)
        if df.empty:
            df['assert'] = 'fail'
            df['assertReason'] = 'No data'
            return df

        df = self._get_peer_matched_df(df)
        if df.empty:
            df['assert'] = 'fail'
            df['assertReason'] = 'No data'
            return df

        df['assertReason'] = [[] for _ in range(len(df))]

        df['assertReason'] += df.apply(self._check_afi_safi, axis=1)

        df['assertReason'] += df.apply(lambda x: ["asn mismatch"]
                                       if x['state'] != "Established" and
                                       (x['peer_y'] and
                                        ((x["asn_x"] != x["peerAsn_y"]) or
                                         (x['asn_y'] != x['peerAsn_x'])))
                                       else [], axis=1)

        # Returning to performing checks even if we didn't get LLDP/Intf info
        df['assertReason'] += df.apply(lambda x:
                                       [f"{x['reason']}:{x['notifcnReason']}"]
                                       if (x['reason'] and
                                           x['state'] != 'Established')
                                       else [],
                                       axis=1)

        df['assertReason'] += df.apply(
            lambda x: ["no route to peer"]
            if x['state'] != "Established" else [],
            axis=1)

        df['assert'] = df.apply(lambda x: 'pass'
                                if not len(x.assertReason) else 'fail',
                                axis=1)

        return (df[['namespace', 'hostname', 'vrf', 'peer_x', 'asn_x',
                    'peerAsn_x', 'state', 'peerHostname', 'vrfPeer',
                    'peer_y', 'asn_y', 'peerAsn_y', 'assert',
                    'assertReason', 'timestamp']]
                .rename(columns={'hostname_x': 'hostname',
                                 'peer_x': 'peer', 'asn_x': 'asn',
                                 'peerAsn_x': 'peerAsn',
                                 'peerHostname_x': 'hostnamePeer',
                                 'peer_y': 'peerPeer',
                                 'asn_y': 'asnPeer',
                                 'peerAsn_y': 'peerAsnPeer'}, copy=False)
                .astype({'asn': 'Int64', 'peerAsn': 'Int64', 'asnPeer': 'Int64',
                         'peerAsnPeer': 'Int64'}, copy=False)
                .explode(column="assertReason")
                .fillna({'assertReason': '-'}))
