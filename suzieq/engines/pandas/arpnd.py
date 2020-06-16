from .engineobj import SqEngineObject


class ArpndObj(SqEngineObject):
    pass

    def get(self, **kwargs):
        """Replacing the original interface name in returned result"""

        addnl_fields = kwargs.pop('addnl_fields', [])
        addnl_fields.append('origIfname')
        df = super().get(addnl_fields=addnl_fields, **kwargs)

        if not df.empty:
            if 'oif' in df.columns:
                df['oif'] = df['origIfname']
            df.drop(columns=['origIfname'], inplace=True)

        return df

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
