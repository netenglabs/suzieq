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
        kwargs.pop('columns', ['default'])
        unknown_tables = []
        tables = []

        for table in table_list:
            table_obj = self._get_table_sqobj(table)

            if not table_obj:
                # This is a table without an sqobject backing store
                # this happens either because we haven't yet implemented the
                # table functions or because this table is collapsed into a
                # single table as in the case of ospf
                unknown_tables.append(table)
                table_inst = self._get_table_sqobj('tables')
                table_inst.table = table
            else:
                table_inst = table_obj

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
                               df['latestTime'].max(),
                               df['intervals'].max(),
                               df['allRows'].sum(),
                               df['namespaces'].max(),
                               df['deviceCnt'].max()]],
                             columns=cols)
        df = df.append(total, ignore_index=True).dropna()
        return df

    def summarize(self, **kwargs):
        '''Summarize metainfo about the various DB tables'''

        df = self.get(**kwargs)

        if df.empty or ('error' in df.columns):
            return df

        df = df.set_index(['table'])

        sdf = pd.DataFrame({
            'serviceCnt': [df.index.nunique()-1],
            'namespaceCnt': [df.at['TOTAL', 'namespaces']],
            'deviceCnt': [df.at['device', 'deviceCnt']],
            'earliestTimestamp': [df.firstTime.min()],
            'lastTimestamp': [df.latestTime.max()],
            'firstTime99': [df.firstTime.quantile(0.99)],
            'latestTime99': [df.latestTime.quantile(0.99)],
        })
        return sdf.T.rename(columns={0: 'summary'})

    def top(self, **kwargs):
        "Tables implementation of top has to eliminate the TOTAL row"

        what = kwargs.pop("what", None)
        reverse = kwargs.pop("reverse", False)
        sqTopCount = kwargs.pop("count", 5)

        if not what:
            return pd.DataFrame()

        df = self.get(**kwargs)
        if df.empty or ('error' in df.columns):
            return df

        if reverse:
            return df.query('table != "TOTAL"') \
                .nsmallest(sqTopCount, columns=what, keep="all") \
                .head(sqTopCount)
        else:
            return df.query('table != "TOTAL"') \
                .nlargest(sqTopCount, columns=what, keep="all") \
                .head(sqTopCount)
