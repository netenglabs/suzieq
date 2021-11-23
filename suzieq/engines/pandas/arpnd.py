import pandas as pd
from .engineobj import SqPandasEngine


class ArpndObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'arpnd'

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
