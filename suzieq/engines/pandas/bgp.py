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
        self._add_field_to_summary('hostname', 'count', 'sessions')
        for field in ['asn', 'vrf']:
            self._add_field_to_summary(field, 'nunique')


        ipv4_enabled = self.summary_df.query("v4Enabled")["namespace"].unique()
        ipv6_enabled = self.summary_df.query("v6Enabled")["namespace"].unique()
        evpn_enabled = self.summary_df.query("evpnEnabled")["namespace"].unique()
        {self.ns[i].update({'afi-safi': []}) for i in self.ns.keys()}
        {self.ns[i]['afi-safi'].append("ipv4")
         for i in self.ns.keys() if i in ipv4_enabled}
        {self.ns[i]['afi-safi'].append("ipv6")
         for i in self.ns.keys() if i in ipv6_enabled}
        {self.ns[i]['afi-safi'].append("evpn")
         for i in self.ns.keys() if i in evpn_enabled}

        established = self.summary_df.query("state == 'Established'") \
            .groupby(by=['namespace'])

        uptime = established["estdTime"]
        self._add_stats_to_summary(uptime, 'upTimes')

        med_v4_updates = established["v4PfxRx"].median()
        med_v6_updates = established["v6PfxRx"].median()
        med_evpn_updates = established["evpnPfxRx"].median()
        med_rx_updates = established["updatesRx"].median()
        med_tx_updates = established["updatesTx"].median()



        {self.ns[i].update({'medV4PfxRx': med_v4_updates[i]})
         for i in med_v4_updates.keys()}
        {self.ns[i].update({'medV6PfxRx': med_v6_updates[i]})
         for i in med_v6_updates.keys()}
        {self.ns[i].update({'medEvpnPfxRx': med_evpn_updates[i]})
         for i in med_evpn_updates.keys()}
        {self.ns[i].update({'medUpdatesRx': med_rx_updates[i]})
         for i in med_rx_updates.keys()}
        {self.ns[i].update({'medUpdatesTx': med_tx_updates[i]})
         for i in med_tx_updates.keys()}

        down_sessions_per_ns = self.summary_df.query("state == 'NotEstd'")['namespace'] \
                                 .value_counts()
        {self.ns[i].update({'downSessions': 0}) for i in self.ns.keys()}
        {self.ns[i].update({'downSessions': down_sessions_per_ns[i]})
         for i in down_sessions_per_ns.keys()}

        return pd.DataFrame(self.ns).convert_dtypes()
