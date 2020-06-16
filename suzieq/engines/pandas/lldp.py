from .engineobj import SqEngineObject


class LldpObj(SqEngineObject):
    pass

    def get(self, **kwargs):
        """Replacing the original interface name in returned result"""

        addnl_fields = kwargs.pop('addnl_fields', [])
        addnl_fields.append('origIfname')
        df = super().get(addnl_fields=addnl_fields, **kwargs)

        if not df.empty:
            if 'ifname' in df.columns:
                df['ifname'] = df['origIfname']
            df.drop(columns=['origIfname'], inplace=True)

        return df

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
