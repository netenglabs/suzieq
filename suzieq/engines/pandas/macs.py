import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class MacsObj(SqPandasEngine):
    '''Backend class to handle manipulating MAC table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'macs'

    # pylint: disable=too-many-statements
    def get(self, **kwargs):
        if not self.iobj.table:
            raise NotImplementedError

        columns = kwargs.pop('columns', ['default'])
        moveCount = kwargs.pop('moveCount', None)
        view = kwargs.pop('view', self.iobj.view)
        remoteOnly = False
        localOnly = kwargs.pop('local', False)
        user_query = kwargs.pop('query_str', '')
        vtep = kwargs.get('remoteVtepIp', [])

        addnl_fields = []

        if vtep:
            if kwargs['remoteVtepIp'] == ['any']:
                del kwargs['remoteVtepIp']
                remoteOnly = True

        if 'moveCount' in columns or (columns == ['*']) or moveCount:
            if view == 'latest':
                view = 'hour'   # compute mac moves only for the last hour
            compute_moves = True
        else:
            compute_moves = False

        fields = self.schema.get_display_fields(columns)
        self._add_active_to_fields(view, fields, addnl_fields)

        user_query_cols = self._get_user_query_cols(user_query)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        df = super().get(view=view, columns=fields, addnl_fields=addnl_fields,
                         **kwargs)

        if columns in [['default'], ['*']] or 'mackey' not in columns:
            if 'mackey' in fields:
                fields.remove('mackey')

        if df.empty:
            return df

        if compute_moves:
            df = df.set_index('namespace hostname mackey macaddr'.split()) \
                   .sort_values(by=['timestamp'])

            # enhanced OIF, capturing both OIF and remoteVtep to capture moves
            # across local and remote
            df['eoif'] = df['oif'] + '-' + df['remoteVtepIp']
            # Check if eoif has changed in the next row. Since we're grouping
            # by the unique entries, OIF + nexthopIP should be only for the
            # provided index
            df['neoif'] = df.groupby(level=[0, 1, 2, 3])[
                'eoif'].shift(1).fillna(value=df['eoif'])
            df['moved'] = df.apply(
                lambda x: 1 if x.neoif != x.eoif else 0, axis=1)
            df['moveCount'] = df.groupby(level=[0, 1, 2, 3])[
                'moved'].cumsum()
            df = df.reset_index()
            if not ((view == "all") or
                    (self.iobj.start_time and self.iobj.end_time)):
                df = df.drop_duplicates(subset=self.schema.key_fields(),
                                        keep='last') \
                    .reset_index(drop=True)

            if moveCount:
                try:
                    moveCount = int(moveCount)
                    df = df.query(
                        f'moveCount == {moveCount}').reset_index(drop=True)
                except ValueError:
                    df = df.query(
                        f'moveCount {moveCount}').reset_index(drop=True)
        elif df.empty and compute_moves:
            df['moveCount'] = []

        df = self._handle_user_query_str(df, user_query)
        if remoteOnly:
            df = df.query("remoteVtepIp != ''").reset_index(drop=True)
        elif localOnly:
            df = df.query("remoteVtepIp == ''").reset_index(drop=True)

        return df[fields]

    def summarize(self, **kwargs):
        """Summarize the MAC table info"""

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('totalMacsinNSCnt', 'hostname', 'count'),
            ('uniqueMacCnt', 'macaddr', 'nunique'),
        ]

        self._summarize_on_perdevice_stat = [
            ('uniqueVlanperHostStat', 'vlan != 0 and vlan != ""', 'vlan',
             'nunique'),
        ]

        return super().summarize(**kwargs)
