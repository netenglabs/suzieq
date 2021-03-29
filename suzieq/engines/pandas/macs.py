from .engineobj import SqPandasEngine


class MacsObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'macs'

    def get(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        columns = kwargs.get('columns', ['default'])
        moveCount = kwargs.pop('moveCount', None)
        view = kwargs.pop('view', self.iobj.view)
        remoteOnly = False
        localOnly = kwargs.pop('localOnly', False)
        user_query = kwargs.pop('query_str', '')
        vtep = kwargs.get('remoteVtepIp', [])

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

        df = self.get_valid_df(self.iobj._table, view=view, **kwargs)

        if compute_moves and not df.empty:
            df = df.set_index('namespace hostname mackey macaddr'.split()) \
                   .sort_values(by=['timestamp'])

            drop_cols = 'eoif neoif moved'.split()

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
            df['moveCount'] = df.groupby(level=[0, 1, 2, 3])['moved'].cumsum()
            df = df.drop(columns=drop_cols).reset_index()

            if 'moveCount' in columns:
                df = df[columns]

            if moveCount:
                try:
                    moveCount = int(moveCount)
                    df = df.query(f'moveCount == {moveCount}').reset_index()
                except ValueError:
                    df = df.query(f'moveCount {moveCount}').reset_index()

        df = self._handle_user_query_str(df, user_query)
        if remoteOnly:
            return df.query("remoteVtepIp != ''")
        elif localOnly:
            return df.query("remoteVtepIp == ''")

        return df

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
