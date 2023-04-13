import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class TableObj(SqPandasEngine):
    '''Backend class for virtual table, tables, with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'tables'

    def get(self, **kwargs):
        """Show the known tables for which we have information"""

        table_list = self._dbeng.get_tables()
        df = pd.DataFrame()
        columns = kwargs.pop('columns', ['default'])
        fields = self.schema.get_display_fields(columns)
        tables = []

        for table in table_list:
            try:
                table_inst = self._get_table_sqobj(table)
            except ModuleNotFoundError:
                # ignore unknown tables
                continue

            info = {'table': table}
            info.update(table_inst.get_table_info(
                columns=['namespace', 'hostname', 'timestamp'],
                **kwargs))
            tables.append(info)

        df = pd.DataFrame.from_dict(tables)
        if df.empty:
            return df

        df = df.sort_values(by=['table']).reset_index(drop=True)
        cols = df.columns
        total = pd.DataFrame([['TOTAL',  df['firstTime'].min(),
                               df['lastTime'].max(),
                               df['intervals'].max(),
                               df['allRows'].sum(),
                               df['namespaceCnt'].max(),
                               df['deviceCnt'].max()]],
                             columns=cols)
        df = pd.concat([df, total]).dropna().reset_index(drop=True)
        return df[fields]

    def summarize(self, **kwargs):
        '''Summarize metainfo about the various DB tables'''

        df = self.get(**kwargs)

        if df.empty or ('error' in df.columns):
            return df

        df = df.set_index(['table'])

        sdf = pd.DataFrame({
            'serviceCnt': [df.index.nunique()-1],
            'namespaceCnt': [df.at['TOTAL', 'namespaceCnt']],
            'deviceCnt': [df.at['device', 'deviceCnt']],
            'earliestTimestamp': [df.firstTime.min()],
            'lastTimestamp': [df.lastTime.max()],
            'firstTime99': [df.firstTime.quantile(0.99)],
            'lastTime99': [df.lastTime.quantile(0.99)],
        })
        return sdf.T.rename(columns={0: 'summary'})

    def top(self, **kwargs):
        "Tables implementation of top has to eliminate the TOTAL row"

        what = kwargs.pop("what", None)
        reverse = kwargs.pop("reverse", False)
        sqTopCount = kwargs.pop("count", 5)

        if not what:
            return pd.DataFrame()

        columns = kwargs.pop('columns', ['default'])
        fields = self.schema.get_display_fields(columns)

        df = self.get(**kwargs)
        if ('error' in df.columns) or df.empty:
            return df

        if reverse:
            df = df.query('table != "TOTAL"') \
                .nsmallest(sqTopCount, columns=what, keep="all") \
                .head(sqTopCount)
        else:
            df = df.query('table != "TOTAL"') \
                .nlargest(sqTopCount, columns=what, keep="all") \
                .head(sqTopCount)

        return df[fields]
