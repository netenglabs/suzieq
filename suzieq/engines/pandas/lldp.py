from .engineobj import SqPandasEngine


class LldpObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'lldp'

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
