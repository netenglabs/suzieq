from .engineobj import SqEngineObject
import pandas as pd
import numpy as np


class BgpObj(SqEngineObject):

    def summarize(self, **kwargs):
        """Summarize key information about BGP"""
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        kwargs.pop('columns', None)
        columns = ['*']

        df = self.get_valid_df(self.iobj._table, sort_fields, columns=columns,
                               **kwargs)
        if df.empty:
            return df

        ns = {i: {} for i in df["namespace"].unique()}
        nsgrp = df.groupby(by=["namespace"])

        hosts_per_ns = nsgrp["hostname"].nunique()
        {ns[i].update({'hosts': hosts_per_ns[i]})
         for i in hosts_per_ns.keys()}

        sessions_per_ns = nsgrp["hostname"].count()
        {ns[i].update({'sessions': sessions_per_ns[i]})
         for i in sessions_per_ns.keys()}

        asns_per_ns = nsgrp["asn"].nunique()
        {ns[i].update({'asns': asns_per_ns[i]})
         for i in asns_per_ns.keys()}

        ipv4_enabled = df.query("v4Enabled")["namespace"].unique()
        ipv6_enabled = df.query("v6Enabled")["namespace"].unique()
        evpn_enabled = df.query("evpnEnabled")["namespace"].unique()
        {ns[i].update({'afi-safi': []}) for i in ns.keys()}
        {ns[i]['afi-safi'].append("ipv4")
         for i in ns.keys() if i in ipv4_enabled}
        {ns[i]['afi-safi'].append("ipv6")
         for i in ns.keys() if i in ipv6_enabled}
        {ns[i]['afi-safi'].append("evpn")
         for i in ns.keys() if i in evpn_enabled}

        # p90 = df.query("state == 'Established'") \
        #         .groupby(by=["namespace"])["estdTime"] \
        #         .apply(lambda x: np.percentile(x, 90))

        med_up_time = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["estdTime"].median()
        max_up_time = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["estdTime"].max()
        min_up_time = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["estdTime"].min()

        {ns[i].update({'upTimes': []}) for i in ns.keys()}
        {ns[i]['upTimes'].append(min_up_time[i]) for i in min_up_time.keys()}
        {ns[i]['upTimes'].append(max_up_time[i]) for i in max_up_time.keys()}
        {ns[i]['upTimes'].append(med_up_time[i]) for i in med_up_time.keys()}

        vrfs = nsgrp["vrf"].nunique()
        {ns[i].update({"vrfs": vrfs[i]}) for i in vrfs.keys()}

        med_v4_updates = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["v4PfxRx"] \
            .median()
        med_v6_updates = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["v6PfxRx"] \
            .median()
        med_evpn_updates = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["evpnPfxRx"] \
            .median()

        {ns[i].update({'medV4PfxRx': med_v4_updates[i]})
         for i in med_v4_updates.keys()}
        {ns[i].update({'medV6PfxRx': med_v6_updates[i]})
         for i in med_v6_updates.keys()}
        {ns[i].update({'medEvpnPfxRx': med_evpn_updates[i]})
         for i in med_evpn_updates.keys()}

        med_rx_updates = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["updatesRx"] \
            .median()
        med_tx_updates = df.query("state == 'Established'") \
            .groupby(by=["namespace"])["updatesTx"] \
            .median()
        {ns[i].update({'medUpdatesRx': med_rx_updates[i]})
         for i in med_rx_updates.keys()}
        {ns[i].update({'medUpdatesTx': med_tx_updates[i]})
         for i in med_tx_updates.keys()}

        down_sessions_per_ns = df.query("state == 'NotEstd'")['namespace'] \
                                 .value_counts()
        {ns[i].update({'downSessions': 0}) for i in ns.keys()}
        {ns[i].update({'downSessions': down_sessions_per_ns[i]})
         for i in down_sessions_per_ns.keys()}

        return(pd.DataFrame(ns).convert_dtypes())
