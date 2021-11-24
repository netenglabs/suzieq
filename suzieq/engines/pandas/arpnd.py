import pandas as pd
from .engineobj import SqPandasEngine


class ArpndObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'arpnd'

    def _check_ipvers(self,  addr: pd.Series, version: int) -> list:

        return addr.apply(lambda a: (
            True if self._get_ipvers(a) == version else False)
            )

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the arpnd table info providing address prefix filtering"""

        prefix = kwargs.pop('prefix', [])
        columns = kwargs.get('columns', [])
        user_query = kwargs.pop('query_str', '')

        addnl_fields = []
        drop_cols = []

        # Always get the ipAddress if there is a filter prefix
        if columns != ['default'] and columns != ['*'] and \
           'ipAddress' not in columns:
            addnl_fields.append('ipAddress')

        df = self.get_valid_df(self.iobj.table,
                               addnl_fields=addnl_fields, **kwargs)

        query_str = ''
        filter_prefix = ''

        for p in prefix:
            query_str += (f'{filter_prefix} '
                          f'@self._is_in_subnet(ipAddress,"{p}")')
            filter_prefix = 'or'

        if query_str:
            df = df.query(query_str)

        df = self._handle_user_query_str(df, user_query)

        return df.drop(columns=drop_cols)

    def summarize(self, **kwargs):
        """Summarize ARPND info across namespace"""
        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('macaddrCnt', 'macaddr', 'count'),
            ('oifCnt', 'oif', 'count'),
            ('uniqueOifCnt', 'oif', 'nunique'),
            ('arpNdEntriesCnt', 'ipAddress', 'count')]

        self._summarize_on_add_with_query = [
            ('arpEntriesCnt', '@self._check_ipvers(ipAddress, 4)',
                'ipAddress'),
            ('v6NDEntriesCnt', '@self._check_ipvers(ipAddress, 6)',
                'ipAddress'),
            ('v6NDGlobalEntriesCnt',
                '@self._check_ipvers(ipAddress, 6) and'
                '@self._is_in_subnet(ipAddress, "fe80::/10")', 'ipAddress'),
            ('v6NDLLAEntriesCnt',
                '@self._check_ipvers(ipAddress, 6) and not '
                '@self._is_in_subnet(ipAddress, "fe80::/10")',
                'ipAddress'),
            ('remoteV4EntriesCnt',
                'state == "remote" and @self._check_ipvers(ipAddress, 4)',
                'ipAddress'),
            ('staticV4EntriesCnt', 'state == "permanent" and '
                '@self._check_ipvers(ipAddress, 4)', 'ipAddress'),
            ('failedV4EntryCnt',
                'state == "failed" and @self._check_ipvers(ipAddress, 4)',
                'ipAddress'),
            ('remoteV6EntriesCnt',
                'state == "remote" and @self._check_ipvers(ipAddress, 6)',
                'ipAddress'),
            ('staticV6EntriesCnt',
                'state == "permanent" and @self._check_ipvers(ipAddress, 6)',
                'ipAddress'),
            ('failedV6EntryCnt',
                'state == "failed" and @self._check_ipvers(ipAddress, 6)',
                'ipAddress')]

        self._check_empty_col = 'arpNdEntriesCnt'
        return super().summarize(**kwargs)
