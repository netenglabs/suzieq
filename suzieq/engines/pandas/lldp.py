import numpy as np
from .engineobj import SqPandasEngine
from suzieq.sqobjects import get_sqobject


class LldpObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'lldp'

    def get(self, **kwargs):
        '''A separate get to handle JunOS MACaddr as peer'''

        addnl_fields = kwargs.get('addnl_fields', [])
        namespace = kwargs.get('namespace', [])
        columns = kwargs.get('columns', [])
        fields = kwargs.get('fields', [])
        dropcols = []

        if columns == ['default']:
            needed_fields = ['subtype', 'peerMacaddr', 'peerIfindex']
        elif 'peerIfname' in columns:
            needed_fields = ['namespace', 'hostname', 'ifname', 'peerHostname',
                             'subtype', 'peerMacaddr', 'peerIfindex']
        else:
            needed_fields = []

        for f in needed_fields:
            if f not in columns:
                addnl_fields.append(f)
                dropcols.append(f)

        df = super().get(addnl_fields=addnl_fields, **kwargs)
        if df.empty or (not needed_fields and columns != ['*']):
            return df

        macdf = df.query('subtype.isin(["", "mac address"])')
        if not macdf.empty:
            macs = df.peerMacaddr.unique().tolist()
            addrdf = get_sqobject('address')(context=self.iobj.ctxt).get(
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
                                                df['ifname_y'], df['peerIfname'])
                    df = df.drop(columns=['hostname_y', 'ifname_y',
                                          'timestamp_y', 'master', 'macaddr'])

        ifidx_df = df.query('subtype.str.startswith("locally")')
        ifindices = ifidx_df.query('peerIfindex != 0').peerIfindex \
            .unique().tolist()
        if not ifidx_df.empty and ifindices:
            ifdf = get_sqobject('interfaces')(context=self.iobj.ctxt).get(
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

        dropcols.extend(['hostname_y', 'ifname_y', 'timestamp_y', 'ifindex'])
        return df.drop(columns=dropcols, errors='ignore')

    def summarize(self, **kwargs):
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
