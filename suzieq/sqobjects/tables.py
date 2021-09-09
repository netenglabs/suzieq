import pandas as pd
from importlib import import_module

from suzieq.sqobjects.basicobj import SqObject
from suzieq.utils import SchemaForTable
from suzieq.db import get_sqdb_engine


class TablesObj(SqObject):

    def __init__(self, **kwargs) -> None:
        # We're passing any table name to get init to work
        super().__init__(table='device', **kwargs)
        self.engine = get_sqdb_engine(self._cfg, None, None, None)
        self._valid_get_args = ['namespace', 'hostname', 'columns', ]

    def get(self, **kwargs):
        """Show the tables for which we have information"""
        if self.columns != ["default"]:
            df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with table']})
            return df

        tables = self.engine.get_tables(**kwargs)
        df = pd.DataFrame()
        unknown_tables = []
        if tables:
            for i, table in enumerate(tables):
                try:
                    module = import_module("suzieq.engines.pandas." + table)
                    eobj = getattr(module, "{}Obj".format(table.title()))
                except ModuleNotFoundError:
                    unknown_tables.append(table)
                    continue

                table_obj = eobj(self)
                info = {'table': table}
                info.update(table_obj.get_table_info(
                    table, columns=['namespace', 'hostname', 'timestamp'],
                    **kwargs))
                tables[i] = info

            if unknown_tables:
                # These are tables for which we don't have processing modules
                # Remove them from the list
                # TODO: Log a warning about these ignored tables
                tables = [x for x in tables if x not in unknown_tables]

            df = pd.DataFrame.from_dict(tables)
            if df.empty:
                return df

            df = df.sort_values(by=['table']).reset_index(drop=True)
            cols = df.columns
            total = pd.DataFrame([['TOTAL',  df['first_time'].min(),
                                   df['latest_time'].max(),
                                   df['intervals'].max(),
                                   df['all rows'].sum(),
                                   df['namespaces'].max(),
                                   df['devices'].max()]],
                                 columns=cols)
            df = df.append(total, ignore_index=True).dropna()
        return df

    def summarize(self, **kwargs):
        raise NotImplementedError
