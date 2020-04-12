from .engineobj import SqEngineObject
import pandas as pd
import re

from suzieq.sqobjects.routes import RoutesObj
from suzieq.sqobjects.lldp import LldpObj
from suzieq.sqobjects.interfaces import IfObj
from suzieq.sqobjects.routes import RoutesObj


def _get_connect_if(row):
    """Given a BGP DF row, retrieve the connecting interface for the row"""
    if re.match(r'^[0-9a-f.:]*$', row['peer']):
        rslt = RoutesObj().lpm(namespace=row['namespace'],
                               hostname=row['hostname'],
                               address=row['peer'], vrf=row['vrf'])
        if not rslt.empty:
            val = rslt['oifs'][0][0]
        else:
            val = ''
    else:
        val = row['peer']
    return val.split('.')[0]


def _check_afi_safi(row) -> list:
    """Checks that AFI/SAFI is compatible across the peers"""

    reasons = ""
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


class BgpObj(SqEngineObject):

    def summarize(self, **kwargs) -> pd.DataFrame:
        """Summarize key information about BGP"""

        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._add_field_to_summary('hostname', 'nunique', 'hosts')
        self._add_field_to_summary('hostname', 'count', 'rows')
        for field in ['asn', 'vrf', 'peerAsn']:
            self._add_list_or_count_to_summary(field)

        ipv4_enabled = self.summary_df.query("v4Enabled")["namespace"].unique()
        ipv6_enabled = self.summary_df.query("v6Enabled")["namespace"].unique()
        evpn_enabled = self.summary_df.query(
            "evpnEnabled")["namespace"].unique()

        established = self.summary_df.query("state == 'Established'") \
            .groupby(by=['namespace'])

        uptime = established["estdTime"]
        v4_updates = established["v4PfxRx"]
        v6_updates = established["v6PfxRx"]
        evpn_updates = established["evpnPfxRx"]
        rx_updates = established["updatesRx"]
        tx_updates = established["updatesTx"]

        down_sessions_per_ns = self.summary_df.query("state == 'NotEstd'")['namespace'] \
            .value_counts()

        self._add_stats_to_summary(uptime, 'upTimes')
        self._add_stats_to_summary(v4_updates, 'v4PfxRx')
        self._add_stats_to_summary(v6_updates, 'v6PfxRx')
        self._add_stats_to_summary(evpn_updates, 'evpnPfxRx')
        self._add_stats_to_summary(rx_updates, 'updatesRx')
        self._add_stats_to_summary(tx_updates, 'updatesTx')

        for i in self.ns.keys():
            self.ns[i].update({'afi-safi': []})
            if i in ipv4_enabled:
                self.ns[i]['afi-safi'].append("ipv4")
            if i in ipv6_enabled:
                self.ns[i]['afi-safi'].append("ipv6")
            if i in evpn_enabled:
                self.ns[i]['afi-safi'].append('evpn')
            self.ns[i].update({'downSessions': down_sessions_per_ns.get(i, 0)})

        self.summary_row_order = ['hosts', 'rows', 'asn', 'peerAsn', 'vrf',
                                  'afi-safi', 'upTimes', 'v4PfxRx',
                                  'v6PfxRx', 'evpnPfxRx', 'updatesRx',
                                  'updatesTx', 'downSessions']
        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def aver(self, **kwargs) -> pd.DataFrame:
        """BGP Assert"""

        assert_cols = ["namespace", "hostname", "vrf", "peer", "asn", "state",
                       "peerAsn", "v4Enabled", "v6Enabled", "evpnEnabled",
                       "v4Advertised", "v6Advertised", "evpnAdvertised",
                       "v4Received", "v6Received", "evpnReceived", "bfdStatus"]

        kwargs.pop("columns", None)  # Loose whatever's passed

        df = self.get(columns=assert_cols, **kwargs)
        if df.empty:
            return pd.DataFrame()

        lldp_df = LldpObj().get(namespace=kwargs.get("namespace", ""),
                                columns=['namespace', 'hostname', 'ifname',
                                         'peerHostname', 'peerIfname'])
        if_df = IfObj().get(namespace=kwargs.get("namespace", ""),
                            columns=['namespace', 'hostname', 'ifname',
                                     'state']) \
            .rename(columns={'state': 'ifState'})

        # Get the dataframes we need for processing
        df['cif'] = df.apply(_get_connect_if, axis=1)
        df = df.merge(if_df, left_on=['namespace', 'hostname', 'cif'],
                      right_on=['namespace', 'hostname', 'ifname'],
                      how='left').drop(columns=['timestamp_y'])

        df = df.merge(lldp_df, left_on=['namespace', 'hostname', 'cif'],
                      right_on=['namespace', 'hostname', 'ifname'],
                      how='left').dropna(how='any', subset=['cif']) \
            .drop(columns=['timestamp', 'ifname_y']) \
            .rename(columns={'timestamp_x': 'timestamp', 'ifname_x': 'ifname'})
        df = df.merge(df, left_on=['namespace', 'hostname', 'vrf', 'cif'],
                      right_on=['namespace', 'peerHostname', 'vrf',
                                'peerIfname'], how='left') \
            .rename(columns={'vrf_x': 'vrf'})
        breakpoint()

        df["assertReason"] = [[] for _ in range(len(df))]
        # Now all sessions with NaN in the oif column have no connected route
        df['assertReason'] += df.apply(
            lambda x: ["no route to peer"] if not len(x['cif_x']) else [],
            axis=1)

        df['assertReason'] += df.apply(
            lambda x: ["peer not configured"] if not x['asn_x'] else [],
            axis=1)

        df['assertReason'] += df.apply(_check_afi_safi, axis=1)

        df['assertReason'] += df.apply(
            lambda x: ["asn mismatch"]
            if x['hostname_y'] and x['asn_x'] and (x["asn_x"] != x["peerAsn_y"])
            else [], axis=1)

        df['assert'] = df.apply(lambda x: 'pass'
                                if not len(x.assertReason) else 'fail',
                                axis=1)
        df.rename(columns={'namespace_x': 'namespace', 'hostname_x': 'hostname',
                           'peer_x': 'peer', 'state_x': 'state'}, inplace=True)
        return (df[['namespace', 'hostname', 'vrf', 'peer', 'state', 'assert',
                    'assertReason']].explode(column="assertReason")
                .fillna({'assertReason': '-'}))
