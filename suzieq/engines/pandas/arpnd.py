from .engineobj import SqPandasEngine


class ArpndObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'arpnd'

    def summarize(self, **kwargs):
        """Summarize ARPND info across namespace"""
        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('arpNdEntriesCnt', 'ipAddress', 'count'),
            ('macaddrCnt', 'macaddr', 'count'),
            ('oifCnt', 'oif', 'count'),
            ('uniqueOifCnt', 'oif', 'nunique')]

        self._summarize_on_add_with_query = [
            ('remoteEntriesCnt', 'state == "remote"', 'ipAddress'),
            ('staticEntriesCnt', 'state == "permanent"', 'ipAddress'),
            ('failedEntryCnt', 'state == "failed"', 'ipAddress')]

        self._check_empty_col = 'arpNdEntriesCnt'
        return super().summarize(**kwargs)
