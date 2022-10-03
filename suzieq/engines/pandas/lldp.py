from typing import List
import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class LldpObj(SqPandasEngine):
    '''Backend class to handle manipulating LLDP table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'lldp'

    def get(self, **kwargs):
        '''A separate get to handle JunOS MACaddr as peer'''

        namespace = kwargs.get('namespace', [])
        columns = kwargs.pop('columns', [])
        use_bond = kwargs.pop('use_bond', "False")
        query_str = kwargs.pop('query_str', '')

        addnl_fields = []
        fields = self.schema.get_display_fields(columns)
        self._add_active_to_fields(kwargs.get('view', self.iobj.view), fields,
                                   addnl_fields)

        if columns == ['default']:
            needed_fields = ['subtype', 'peerMacaddr', 'peerIfindex']
        elif 'peerIfname' in columns:
            needed_fields = ['namespace', 'hostname', 'ifname', 'peerHostname',
                             'subtype', 'peerMacaddr', 'peerIfindex']
        else:
            needed_fields = []

        addnl_fields += [f for f in needed_fields if f not in fields]

        user_query_cols = self._get_user_query_cols(query_str)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        df = super().get(addnl_fields=addnl_fields, columns=fields, **kwargs)
        if df.empty:
            return df
        if not needed_fields and columns != ['*']:
            return df[fields]

        macdf = df.query('subtype.isin(["", "mac address"])')
        if not macdf.empty:
            macs = macdf.peerMacaddr.unique().tolist()
            addrdf = self._get_table_sqobj('address').get(
                namespace=namespace, address=macs,
                columns=['namespace', 'hostname', 'ifname', 'macaddr'])

            if not addrdf.empty:
                df = df.merge(
                    addrdf, how='left',
                    left_on=['namespace', 'peerHostname', 'peerMacaddr'],
                    right_on=['namespace', 'hostname', 'macaddr'],
                    suffixes=['', '_y']) \
                    .fillna({'ifname_y': '-'}) \

                if not df.empty:
                    df['peerIfname'] = np.where(df['peerIfname'] == '-',
                                                df['ifname_y'],
                                                df['peerIfname'])
                    df = df.drop(columns=['hostname_y', 'ifname_y',
                                          'timestamp_y', 'vrf', 'macaddr'],
                                 errors='ignore')

        ifidx_df = df.query('subtype.str.startswith("locally")')
        # stringify the numbers because sqobj expects pretty much all input
        # to be strings
        ifindices = [str(x)
                     for x in ifidx_df.query('peerIfindex != 0').peerIfindex
                     .unique().tolist()]
        if not ifidx_df.empty and ifindices:
            ifdf = self._get_table_sqobj('interfaces').get(
                namespace=namespace, ifindex=ifindices,
                columns=['namespace', 'hostname', 'ifname', 'ifindex'])
            df = df.merge(
                ifdf, how='left',
                left_on=['namespace', 'peerHostname', 'peerIfindex'],
                right_on=['namespace', 'hostname', 'ifindex'],
                suffixes=['', '_y']) \
                .fillna({'ifname_y': '-'})

            if not df.empty:
                df['peerIfname'] = np.where(df['peerIfname'] == '-',
                                            df['ifname_y'], df['peerIfname'])

        if use_bond.lower() == "true":
            df = self._resolve_to_bond(
                df[fields], hostname=kwargs.get('hostname', []))[fields]

        df = self._handle_user_query_str(df, query_str)
        return df.reset_index(drop=True)[fields]

    def summarize(self, **kwargs):
        '''Summarize LLDP info'''
        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('nbrCnt', 'hostname', 'count'),
            ('peerHostnameCnt', 'peerHostname', 'count'),
            ('uniquePeerMgmtIPCnt', 'mgmtIP', 'nunique'),
        ]

        self._summarize_on_add_with_query = [
            ('missingPeerInfoCnt', "mgmtIP == '-' or mgmtIP == ''", 'mgmtIP')
        ]

        return super().summarize(**kwargs)

    def _resolve_to_bond(self, df: pd.DataFrame,
                         hostname=List[str]) -> pd.DataFrame:
        """Change bond/channel member ports into bond name

        With normal port channels or bond interfaces, this routine
        replaces the ifname and peerifname with the appropriate bond
        name.

        Args:
            df: The original LLDP dataframe
            hostname: The hostname selection passed by user

        Returns:
            The LLDP dataframe with the appropriate substitution
        """

        ifdf = self._get_table_sqobj('interfaces').get(
            namespace=df.namespace.unique().tolist(),
            hostname=hostname,
            type=['bond_slave', 'bond'],
            columns=['namespace', 'hostname', 'ifname', 'adminState',
                     'ipAddressList', 'master', 'mtu'])

        if ifdf.empty:
            # Could we do something better, probably. TBD.
            return df

        # OSPF sessions maybe over a port-channel. Make LLDP
        # matchup
        lldp_df = df.merge(ifdf, on=['namespace', 'hostname', 'ifname'],
                           how='left')
        lldp_df = lldp_df.merge(
            ifdf,
            left_on=['namespace', 'peerHostname', 'peerIfname'],
            right_on=['namespace', 'hostname', 'ifname'],
            how='left', suffixes=['', '_peer']) \
            .replace(to_replace={'master': {'bridge': np.nan,
                                            'default': np.nan,
                                            '': np.nan},
                                 'master_peer': {'bridge': np.nan,
                                                 'default': np.nan,
                                                 '': np.nan}})

        lldp_df['ifname'] = np.where(~lldp_df.master.isnull(),
                                     lldp_df.master, lldp_df.ifname)
        lldp_df['peerIfname'] = np.where(~lldp_df.master_peer.isnull(),
                                         lldp_df.master_peer,
                                         lldp_df.peerIfname)
        lldp_df = lldp_df.drop_duplicates(
            subset=['namespace', 'hostname', 'ifname']) \
            .drop(columns=['master', 'master_peer'], errors='ignore')

        return lldp_df
