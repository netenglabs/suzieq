import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.shared.utils import build_query_str, humanize_timestamp


class BgpObj(SqPandasEngine):
    '''Backend class to handle manipulating BGP table with pandas'''

    def __init__(self, baseobj):
        super().__init__(baseobj)
        self._assert_result_cols = ['namespace', 'hostname', 'vrf', 'peer',
                                    'asn', 'peerAsn', 'state', 'peerHostname',
                                    'result', 'assertReason', 'timestamp']

    @staticmethod
    def table_name():
        '''Table name'''
        return 'bgp'

    def get(self, **kwargs):
        """Replacing the original interface name in returned result"""

        columns = kwargs.pop('columns', ['default'])
        vrf = kwargs.pop('vrf', None)
        peer = kwargs.pop('peer', None)
        hostname = kwargs.pop('hostname', None)
        user_query = kwargs.pop('query_str', None)
        afi_safi = kwargs.pop('afiSafi', '')

        addnl_fields = ['origPeer']
        sch = self.schema
        fields = sch.get_display_fields(columns)

        self._add_active_to_fields(kwargs.get('view', self.iobj.view), fields,
                                   addnl_fields)

        for col in ['peerIP', 'updateSource', 'state', 'namespace', 'vrf',
                    'peer', 'hostname']:
            if col not in fields:
                addnl_fields.append(col)

        if afi_safi and afi_safi not in fields:
            addnl_fields.append('afiSafi')

        user_query_cols = self._get_user_query_cols(user_query)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        try:
            df = super().get(addnl_fields=addnl_fields, columns=fields,
                             **kwargs)
        except KeyError as ex:
            if ('afi' in str(ex)) or ('safi' in str(ex)):
                df = pd.DataFrame(
                    {'error':
                     ['ERROR: Migrate BGP data first using sq-coalescer']})
                return df

        if df.empty:
            # We cannot add df[fields] here because we haven't added the
            # augmented columns yet and so can fail.
            return df

        if afi_safi or 'afiSafi' in fields or (columns == ['*']):
            df['afiSafi'] = df['afi'] + ' ' + df['safi']
        query_str = build_query_str([], sch, vrf=vrf, peer=peer,
                                    hostname=hostname, afiSafi=afi_safi,
                                    ignore_regex=False)
        if 'peer' in df.columns:
            df['peer'] = np.where(df['origPeer'] != "",
                                  df['origPeer'], df['peer'])

        if 'asndot' in fields:
            df['asndot'] = df.asn.apply(lambda x: f'{int(x/65536)}.{x%65536}')

        if 'peerAsndot' in fields:
            df['peerAsndot'] = df.peerAsn.apply(
                lambda x: f'{int(x/65536)}.{x%65536}')

        # Convert old data into new 2.0 data format
        if 'peerHostname' in df.columns:
            mdf = self._get_peer_matched_df(df)
        else:
            mdf = df

        mdf = self._handle_user_query_str(mdf, user_query)

        if query_str:
            return mdf.query(query_str).reset_index(drop=True)[fields]
        else:
            return mdf.reset_index(drop=True)[fields]

    def summarize(self, **kwargs) -> pd.DataFrame:
        """Summarize key information about BGP"""

        self._init_summarize(**kwargs)
        if self.summary_df.empty or ('error' in self.summary_df.columns):
            return self.summary_df

        self.summary_df['afiSafi'] = (
            self.summary_df['afi'] + ' ' + self.summary_df['safi'])

        afi_safi_count = self.summary_df.groupby(by=['namespace'])['afiSafi'] \
                                        .nunique()

        self.summary_df = self.summary_df \
                              .set_index(['namespace', 'hostname', 'vrf',
                                          'peer']) \
                              .query('~index.duplicated(keep="last")') \
                              .reset_index()
        self.ns = {i: {} for i in self.summary_df['namespace'].unique()}
        self.nsgrp = self.summary_df.groupby(by=["namespace"],
                                             observed=True)

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('totalPeerCnt', 'peer', 'count'),
            ('uniqueAsnCnt', 'asn', 'nunique'),
            ('uniqueVrfsCnt', 'vrf', 'nunique')
        ]

        self._summarize_on_add_with_query = [
            ('failedPeerCnt', 'state == "NotEstd"', 'peer'),
            ('iBGPPeerCnt', 'asn == peerAsn', 'peer', 'count'),
            ('eBGPPeerCnt', 'asn != peerAsn', 'peer', 'count'),
            ('rrClientPeerCnt', 'rrclient.str.lower() == "true"', 'peer',
             'count'),
        ]

        self._gen_summarize_data()

        # pylint: disable=expression-not-assigned
        {self.ns[i].update({'activeAfiSafiCnt': afi_safi_count[i]})
         for i in self.ns.keys()}
        self.summary_row_order.append('activeAfiSafiCnt')

        self.summary_df['estdTime'] = humanize_timestamp(
            self.summary_df.estdTime,
            self.cfg.get('analyzer', {}).get('timezone', None))

        self.summary_df['estdTime'] = (
            self.summary_df['timestamp'] - self.summary_df['estdTime'])
        self.summary_df['estdTime'] = self.summary_df['estdTime'] \
                                          .apply(lambda x: x.round('s'))
        # Now come the BGP specific ones
        established = self.summary_df.query("state == 'Established'") \
            .groupby(by=['namespace'])

        uptime = established["estdTime"]
        rx_updates = established["updatesRx"]
        tx_updates = established["updatesTx"]
        self._add_stats_to_summary(uptime, 'upTimeStat')
        self._add_stats_to_summary(rx_updates, 'updatesRxStat')
        self._add_stats_to_summary(tx_updates, 'updatesTxStat')

        self.summary_row_order.extend(['upTimeStat', 'updatesRxStat',
                                       'updatesTxStat'])

        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def _get_peer_matched_df(self, df) -> pd.DataFrame:
        """Get a BGP dataframe that also contains a session's matching peer"""

        if 'peerHostname' not in df.columns:
            return df

        # We have to separate out the Established and non Established entries
        # for the merge. Otherwise we end up with a mess
        df_1 = df[['namespace', 'hostname', 'vrf', 'peer', 'peerIP',
                   'updateSource']] \
            .drop_duplicates() \
            .reset_index(drop=True)
        df_2 = df[['namespace', 'hostname', 'vrf', 'updateSource']] \
            .drop_duplicates() \
            .reset_index(drop=True)

        mdf = df_1.merge(df_2,
                         left_on=['namespace', 'peerIP'],
                         right_on=['namespace', 'updateSource'],
                         suffixes=('', '_y')) \
            .drop_duplicates(subset=['namespace', 'hostname', 'vrf',
                                     'peerIP']) \
            .rename(columns={'hostname_y': 'peerHost'}) \
            .fillna(value={'peerHostname': '', 'peerHost': ''}) \
            .reset_index(drop=True)

        df = df.merge(mdf[['namespace', 'hostname', 'vrf', 'peer',
                           'peerHost']],
                      on=['namespace', 'hostname', 'vrf', 'peer'], how='left')

        df['peerHostname'] = np.where((df['peerHostname'] == '') &
                                      (df['state'] == "Established"),
                                      df['peerHost'],
                                      df['peerHostname'])
        df = df.fillna(value={'peerHostname': ''}) \
            .drop(columns=['peerHost'])

        for i in df.select_dtypes(include='category'):
            df[i].cat.add_categories('', inplace=True)

        return df

    def aver(self, **kwargs) -> pd.DataFrame:
        """BGP Assert"""

        def _check_if_state(row, if_df):

            if not if_df.empty:
                thisif = if_df.query(f'namespace=="{row.namespace}" and '
                                     f'hostname=="{row.hostname}" and '
                                     f'ifname=="{row.ifname}"')
                if not thisif.empty:
                    if thisif.adminState.unique()[0] != 'up':
                        return ['interface admin down']
                    elif thisif.state.unique()[0] != 'up':
                        return ['interface down']
                    else:
                        return []

            return []

        assert_cols = ["namespace", "hostname", "vrf", "peer", "peerHostname",
                       "afi", "safi", "asn", "state", "peerAsn", "bfdStatus",
                       "reason", "notificnReason", "afisAdvOnly", 'ifname',
                       "afisRcvOnly", "peerIP", "updateSource", "timestamp"]

        kwargs.pop("columns", None)  # Loose whatever's passed
        result = kwargs.pop("result", 'all')
        state = kwargs.pop('state', '!dynamic')

        df = self.get(columns=assert_cols, state=state, **kwargs)
        if 'error' in df:
            return df

        if df.empty:
            if result != "pass":
                df['result'] = 'fail'
                df['assertReason'] = 'No data'
            return df

        df = self._get_peer_matched_df(df)
        if df.empty:
            if result != "pass":
                df['result'] = 'fail'
                df['assertReason'] = 'No data'
            return df

        # We can get rid of sessions with duplicate peer info since we're
        # interested only in session info here
        df = df.drop_duplicates(
            subset=['namespace', 'hostname', 'vrf', 'peer'])

        failed_df = df.query("state != 'Established'").reset_index(drop=True)
        passed_df = df.query("state == 'Established'").reset_index(drop=True)

        # Get the interface information
        if_df = self._get_table_sqobj('interfaces').get(
            namespace=failed_df.namespace.unique().tolist(),
            hostname=failed_df.hostname.unique().tolist(),
            ifname=failed_df.ifname.unique().tolist(),
            columns=['namespace', 'hostname', 'ifname', 'state', 'adminState']
        )

        failed_df['assertReason'] = [[] for _ in range(len(failed_df))]
        passed_df['assertReason'] = [[] for _ in range(len(passed_df))]

        if not failed_df.empty:
            # For not established entries, check if route/ARP entry exists
            failed_df['assertReason'] += failed_df.apply(
                _check_if_state, args=(if_df,), axis=1)

            failed_df['assertReason'] += failed_df.apply(
                lambda x: ["asn mismatch"]
                if (x['peerHostname'] and ((x["asn"] != x["peerAsn_y"]) or
                                           (x['asn_y'] != x['peerAsn'])))
                else [], axis=1)

            failed_df['assertReason'] += failed_df.apply(
                lambda x: [f"{x['reason']}:{x['notificnReason']}"]
                if ((x['reason'] and x['reason'] != 'None' and
                     x['reason'] != "No error"))
                else [], axis=1)

            failed_df['result'] = 'fail'

        # Get list of peer IP addresses for peer not in Established state
        # Returning to performing checks even if we didn't get LLDP/Intf info

        if not passed_df.empty:
            passed_df['assertReason'] += passed_df.apply(
                lambda x: ['Not all Afi/Safis enabled']
                if x['afisAdvOnly'].any() or x['afisRcvOnly'].any() else [],
                axis=1)

            passed_df['result'] = passed_df.apply(
                lambda x: 'pass'
                if len(x.assertReason) == 0 else 'fail',
                axis=1)

        df = pd.concat([failed_df, passed_df])

        result_df = df[self._assert_result_cols] \
            .explode(column="assertReason") \
            .fillna({'assertReason': '-'})

        if result == "fail":
            result_df = result_df.query('assertReason != "-"')
        elif result == "pass":
            result_df = result_df.query('assertReason == "-"')

        return result_df.reset_index(drop=True)
