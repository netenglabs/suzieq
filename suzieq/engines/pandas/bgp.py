from .engineobj import SqEngineObject
import pandas as pd
import numpy as np


class BgpObj(SqEngineObject):

    def summarize(self, **kwargs):
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
        evpn_enabled = self.summary_df.query("evpnEnabled")["namespace"].unique()

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
