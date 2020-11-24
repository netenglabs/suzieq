from suzieq.sqobjects.address import AddressObj

import pandas as pd
import numpy as np

from .engineobj import SqEngineObject
from suzieq.utils import build_query_str, SchemaForTable


class BgpObj(SqEngineObject):

    def get(self, **kwargs):
        """Replacing the original interface name in returned result"""

        addnl_fields = kwargs.pop('addnl_fields', [])
        columns = kwargs.get('columns', ['default'])
        vrf = kwargs.pop('vrf', None)
        peer = kwargs.pop('peer', None)
        hostname = kwargs.pop('hostname', None)

        drop_cols = ['origPeer', 'peerHost']
        addnl_fields.extend(['origPeer'])

        if columns != ['*']:
            if 'peerIP' not in columns:
                addnl_fields.append('peerIP')
                drop_cols.append('peerIP')
            if 'updateSource' not in columns:
                addnl_fields.append('updateSource')
                drop_cols.append('updateSource')

        df = super().get(addnl_fields=addnl_fields, **kwargs)

        if df.empty:
            return df

        sch = SchemaForTable(self.iobj.table, self.schemas)
        query_str = build_query_str([], sch, vrf=vrf, peer=peer,
                                    hostname=hostname)
        if 'peer' in df.columns:
            df['peer'] = np.where(df['origPeer'] != "",
                                  df['origPeer'], df['peer'])
        if 'peerHostname' in df.columns:
            mdf = self._get_peer_matched_df(df)
            drop_cols = [x for x in drop_cols if x in mdf.columns]
            drop_cols.extend(list(mdf.filter(regex='_y')))
        else:
            mdf = df

        if query_str:
            return mdf.query(query_str).drop(columns=drop_cols,
                                             errors='ignore')
        else:
            return mdf.drop(columns=drop_cols, errors='ignore')

    def _check_afi_safi(self, row) -> list:
        """Checks that AFI/SAFI is compatible across the peers"""

        reasons = ""
        if not row['peer_y']:
            return []

        if row["v4Enabled"] != row["v4Enabled_y"]:
            if row["v4Advertised"] and not row["v4Received"]:
                reasons += " peer not advertising ipv4/unicast"
            elif row["v4Received"] and not row["v4Advertised"]:
                reasons += " not advertising ipv4/unicast"
        if row["v6Enabled"] != row["v6Enabled_y"]:
            if row["v6Advertised"] and not row["v6Received"]:
                reasons += " peer not advertising ipv6/unicast"
            elif row["v6Received"] and not row["v6Advertised"]:
                reasons += " not advertising ipv6/unicast"
        if row["evpnEnabled"] != row["evpnEnabled_y"]:
            if row["evpnAdvertised"] and not row["evpnReceived"]:
                reasons += " peer not advertising evpn"
            elif row["evpnReceived"] and not row["evpnAdvertised"]:
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

        # We have to separate out the Established and non Established entries
        # for the merge. Otherwise we end up with a mess
        estd_df = df[df.state == 'Established']
        if not estd_df.empty:
            mestd_df = estd_df.merge(estd_df, left_on=['namespace', 'peerIP'],
                                     right_on=['namespace', 'updateSource'],
                                     how='left',
                                     suffixes=('', '_y')) \
                .drop_duplicates(subset=['namespace', 'hostname', 'vrf',
                                         'peer']) \
                .rename(columns={'hostname_y': 'peerHost'})
            # I've not seen the diff between ignore_index and not and so
            # deliberately ignoring
            mdf = mestd_df.append(df[df.state != 'Established'])
            # Pandas 1.1.1 insists on fill values being in category already
            for i in mdf.select_dtypes(include='category'):
                mdf[i].cat.add_categories('', inplace=True)
            mdf.fillna(value={'peerHostname': '', 'vrf_y': '', 'peer_y': '',
                              'peerHost': '', 'asn_y': 0, 'peerAsn_y': 0},
                       inplace=True)

            if 'peerHostname' in df.columns:
                mdf['peerHostname'] = np.where(mdf['state'] == 'Established',
                                               mdf['peerHost'],
                                               mdf['peerHostname'])
            else:
                mdf.rename(columns={'peerHost': 'peerHostname'}, inplace=True)
        else:
            mdf = df

        return mdf

    def aver(self, **kwargs) -> pd.DataFrame:
        """BGP Assert"""

        assert_cols = ["namespace", "hostname", "vrf", "peer", "asn", "state",
                       "peerAsn", "v4Enabled", "v6Enabled", "evpnEnabled",
                       "v4Advertised", "v6Advertised", "evpnAdvertised",
                       "v4Received", "v6Received", "evpnReceived", "bfdStatus",
                       "reason", "notificnReason", "peerIP", "updateSource"]

        kwargs.pop("columns", None)  # Loose whatever's passed
        status = kwargs.pop("status", 'all')

        df = self.get(columns=assert_cols, state='!dynamic', **kwargs)
        if df.empty:
            if status != "pass":
                df['assert'] = 'fail'
                df['assertReason'] = 'No data'
            return df

        df = self._get_peer_matched_df(df)
        df = df.rename(columns={'vrf_y': 'vrfPeer', 'peerIP_y': 'peerPeerIP'}) \
               .drop(columns={'state_y', 'reason_y', 'timestamp_y'})
        if df.empty:
            if status != "pass":
                df['assert'] = 'fail'
                df['assertReason'] = 'No data'
            return df

        df['assertReason'] = [[] for _ in range(len(df))]

        df['assertReason'] += df.apply(self._check_afi_safi, axis=1)

        df['assertReason'] += df.apply(lambda x: ["asn mismatch"]
                                       if x['state'] != "Established" and
                                       (x['peerHostname'] and
                                        ((x["asn"] != x["peerAsn_y"]) or
                                         (x['asn_y'] != x['peerAsn'])))
                                       else [], axis=1)

        # Get list of peer IP addresses for peer not in Established state
        # Returning to performing checks even if we didn't get LLDP/Intf info
        df['assertReason'] += df.apply(
            lambda x: [f"{x['reason']}:{x['notificnReason']}"]
            if ((x['state'] != 'Established') and
                (x['reason'] and x['reason'] != 'None' and
                 x['reason'] != "No error"))
            else [],
            axis=1)

        df['assertReason'] += df.apply(
            lambda x: ['Matching BGP Peer not found']
            if x['state'] == 'NotEstd' and not x['assertReason']
            else [],  axis=1)

        df['assert'] = df.apply(lambda x: 'pass'
                                if not len(x.assertReason) else 'fail',
                                axis=1)

        result = df[['namespace', 'hostname', 'vrf', 'peer', 'asn',
                     'peerAsn', 'state', 'peerHostname', 'vrfPeer',
                     'peer_y', 'asn_y', 'peerAsn_y', 'assert',
                     'assertReason', 'timestamp']] \
            .rename(columns={'peer_y': 'peerPeer',
                             'asn_y': 'asnPeer',
                             'peerAsn_y': 'peerAsnPeer'}, copy=False) \
            .astype({'asn': 'Int64', 'peerAsn': 'Int64',
                     'asnPeer': 'Int64',
                     'peerAsnPeer': 'Int64'}, copy=False) \
            .explode(column="assertReason") \
            .fillna({'assertReason': '-'})

        if status == "fail":
            return result.query('assertReason != "-"')
        elif status == "pass":
            return result.query('assertReason == "-"')

        return result
