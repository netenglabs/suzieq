from .engineobj import SqEngineObject


class LldpObj(SqEngineObject):
    pass

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
