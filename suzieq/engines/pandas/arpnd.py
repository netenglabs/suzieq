import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class ArpndObj(SqPandasEngine):
    '''Backend pandas engine class to support manipulating ARP/ND table'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'arpnd'

    def get(self, **kwargs) -> pd.DataFrame:
        """Retrieve the arpnd table info providing address prefix filtering"""

        prefix = kwargs.pop('prefix', [])
        columns = kwargs.pop('columns', [])
        user_query = kwargs.pop('query_str', '')
        view = kwargs.get('view', self.iobj.view)

        addnl_fields = []
        # Always get the ipAddress if there is a filter prefix
        fields = self.schema.get_display_fields(columns)
        if 'ipAddress' not in fields:
            addnl_fields.append('ipAddress')

        self._add_active_to_fields(view, fields, addnl_fields)
        user_query_cols = self._get_user_query_cols(user_query)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        df = super().get(addnl_fields=addnl_fields, columns=fields, **kwargs)

        query_str = ''
        filter_prefix = ''

        for p in prefix:
            query_str += (f'{filter_prefix} '
                          f'@self._is_in_subnet(ipAddress,"{p}")')
            filter_prefix = 'or'

        if query_str:
            df = df.query(query_str)

        df = self._handle_user_query_str(df, user_query)

        return df.reset_index(drop=True)[fields]

    def summarize(self, **kwargs):
        """Summarize ARPND info across namespace"""
        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('arpNdEntriesCnt', 'ipAddress', 'count'),
            ('uniqueArpEntriesCnt', 'ipAddress', 'nunique'),
            ('uniqueOifCnt', 'oif', 'nunique')]

        self._summarize_on_add_with_query = [
            ('arpEntriesCnt', '@self._check_ipvers(ipAddress, 4)',
                'ipAddress'),
            ('v6NDEntriesCnt', '@self._check_ipvers(ipAddress, 6)',
                'ipAddress'),
            ('v6NDGlobalEntriesCnt',
                '@self._check_ipvers(ipAddress, 6) and '
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
            ('remoteV6EntriesCnt',
                'state == "remote" and @self._check_ipvers(ipAddress, 6)',
                'ipAddress'),
            ('staticV6EntriesCnt',
                'state == "permanent" and @self._check_ipvers(ipAddress, 6)',
                'ipAddress'),
            ('failedEntriesCnt', 'state == "failed"', 'ipAddress'),
            ('failedV4EntriesCnt',
                'state == "failed" and @self._check_ipvers(ipAddress, 4)',
                'ipAddress'),
            ('failedV6EntriesCnt',
                'state == "failed" and @self._check_ipvers(ipAddress, 6)',
                'ipAddress')]

        self._check_empty_col = 'arpNdEntriesCnt'
        return super().summarize(**kwargs)
