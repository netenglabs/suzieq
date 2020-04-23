from suzieq.sqobjects.routes import RoutesObj
from suzieq.sqobjects.interfaces import IfObj
from suzieq.sqobjects.lldp import LldpObj

import re
import pandas as pd

from .engineobj import SqEngineObject


class BgpObj(SqEngineObject):

    def _get_connect_if(self, row) -> str:
        """Given a BGP DF row, retrieve the connecting interface for the row"""
        if re.match(r'^[0-9a-f.:]*$', row['peer']):
            rslt = RoutesObj(context=self.ctxt).lpm(namespace=row['namespace'],
                                                    hostname=row['hostname'],
                                                    address=row['peer'],
                                                    vrf=row['vrf'])
            if not rslt.empty:
                val = rslt['oifs'][0][0]
            else:
                val = ''
        else:
            val = row['peer']
        return val

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
        ]

        self._summarize_on_add_list_or_count = [
            ('uniqueAsnCnt', 'asn'),
            ('uniqueVrfsCnt', 'vrf')
        ]

        self._summarize_on_add_with_query = [
            ('failedPeerCnt', 'state == "NotEstd"', 'peer')
        ]

        self._gen_summarize_data()

        # Now come the BGP specific ones
        established = self.summary_df.query("state == 'Established'") \
            .groupby(by=['namespace'])

        uptime = established["estdTime"]
        v4_updates = established["v4PfxRx"]
        v6_updates = established["v6PfxRx"]
        evpn_updates = established["evpnPfxRx"]
        rx_updates = established["updatesRx"]
        tx_updates = established["updatesTx"]

        self._add_stats_to_summary(uptime, 'upTimesStat')
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

    def aver(self, **kwargs) -> pd.DataFrame:
        """BGP Assert"""

        assert_cols = ["namespace", "hostname", "vrf", "peer", "asn", "state",
                       "peerAsn", "v4Enabled", "v6Enabled", "evpnEnabled",
                       "v4Advertised", "v6Advertised", "evpnAdvertised",
                       "v4Received", "v6Received", "evpnReceived", "bfdStatus",
                       "reason", "notifcnReason"]

        kwargs.pop("columns", None)  # Loose whatever's passed

        df = self.get(columns=assert_cols, **kwargs)
        if df.empty:
            return pd.DataFrame()

        if_df = IfObj(context=self.ctxt).get(namespace=kwargs.get("namespace", ""),
                                             columns=['namespace', 'hostname',
                                                      'ifname', 'state']) \
            .rename(columns={'state': 'ifState'})

        lldp_df = LldpObj(context=self.ctxt).get(
            namespace=kwargs.get("namespace", ""),
            columns=['namespace', 'hostname', 'ifname', 'peerHostname',
                     'peerIfname'])

        # Get the dataframes we need for processing
        df['cif'] = df.apply(self._get_connect_if, axis=1)
        df['ifname'] = df['cif'].str.split('.').str[0]

        df = df.merge(if_df, left_on=['namespace', 'hostname', 'cif'],
                      right_on=['namespace', 'hostname', 'ifname'],
                      how='left') \
            .drop(columns=['timestamp_y', 'ifname_y']) \
            .rename(columns={'ifname_x': 'ifname'})

        # We split off at this point to avoid merging mess because of lack of
        # LLDP info
        df = df.merge(lldp_df, on=['namespace', 'hostname', 'ifname'], how='left') \
               .drop(columns=['timestamp']) \
               .rename(columns={'timestamp_x': 'timestamp'})
        # Some munging to handle subinterfaces
        df['xx'] = df['peerIfname'] + '.' + df['cif'].str.split('.').str[1]

        df['peerIfname'] = df['xx'].where(
            df['xx'].notnull(), df['peerIfname'])
        df.drop(columns=['xx'], inplace=True)

        df = df.merge(df, left_on=['namespace', 'hostname', 'cif'],
                      right_on=['namespace', 'peerHostname',
                                'peerIfname'], how='left') \
            .drop(columns=['peerIfname_y', 'timestamp_y', 'cif_y',
                           'ifState_y', 'reason_y', 'notifcnReason_y']) \
            .rename(columns={'timestamp_x': 'timestamp',
                             'cif_x': 'cif', 'ifState_x': 'ifState',
                             'reason_x': 'reason',
                             'notifcnReason_x': 'notifcnReason'})
        df['peer_y'] = df['peer_y'].astype(str) \
                                   .where(df['peer_y'].notnull(), '')
        df["assertReason"] = [[] for _ in range(len(df))]
        # Now all sessions with NaN in the oif column have no connected route
        df['assertReason'] += df.apply(
            lambda x: ["outgoing link down"]
            if x['cif'] and x['ifState'] != "up" else [],
            axis=1)

        df['assertReason'] += df.apply(
            lambda x: ["no route to peer"] if not len(x['cif']) else [],
            axis=1)

        df['assertReason'] += df.apply(self._check_afi_safi, axis=1)

        df['assertReason'] += df.apply(lambda x: ["asn mismatch"] if x['peer_y']
                                       and ((x["asn_x"] != x["peerAsn_y"]) or
                                            (x['asn_y'] != x['peerAsn_x']))
                                       else [], axis=1)

        df['assertReason'] += df.apply(lambda x:
                                       [f"{x['reason']}:{x['notifcnReason']}"]
                                       if (x['reason'] and
                                           x['state_x'] != 'Established') else [],
                                       axis=1)

        df['assert'] = df.apply(lambda x: 'pass'
                                if not len(x.assertReason) else 'fail',
                                axis=1)
        return (df[['namespace', 'hostname_x', 'vrf_x', 'peer_x', 'asn_x',
                    'peerAsn_x', 'state_x', 'peerHostname_x', 'vrf_y', 'peer_y',
                    'asn_y', 'peerAsn_y', 'assert',
                    'assertReason', 'timestamp']]
                .rename(columns={'hostname_x': 'hostname', 'vrf_x':
                                 'vrf', 'peer_x': 'peer', 'asn_x': 'asn',
                                 'peerAsn_x': 'peerAsn', 'state_x': 'state',
                                 'peerHostname_x': 'hostnamePeer',
                                 'vrf_y': 'vrfPeer', 'peer_y': 'peerPeer',
                                 'asn_y': 'asnPeer',
                                 'peerAsn_y': 'peerAsnPeer'}, copy=False)
                .explode(column="assertReason")
                .astype({'asn': 'Int64', 'peerAsn': 'Int64', 'asnPeer': 'Int64',
                         'peerAsnPeer': 'Int64'}, copy=False)
                .fillna({'assertReason': '-'}))
