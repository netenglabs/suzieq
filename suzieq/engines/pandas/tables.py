import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.sqobjects import get_sqobject


class TableObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'tables'

    def get(self, **kwargs):
        """Show the known tables for which we have information"""

        table_list = self._dbeng.get_tables()
        df = pd.DataFrame()
        columns = kwargs.pop('columns', ['default'])
        unknown_tables = []
        tables = []

        for table in table_list:
            table_obj = get_sqobject(table)

            if not table_obj:
                # This is a table without an sqobject backing store
                # this happens either because we haven't yet implemented the
                # table functions or because this table is collapsed into a
                # single table as in the case of ospf
                unknown_tables.append(table)
                table_inst = get_sqobject('tables')(context=self.ctxt)
                table_inst._table = table
            else:
                table_inst = table_obj(context=self.ctxt)

            info = {'table': table}
            info.update(table_inst.get_table_info(
                table, columns=['namespace', 'hostname', 'timestamp'],
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
