import pandas as pd
from importlib import import_module

from suzieq.sqobjects import basicobj
from suzieq.utils import SchemaForTable


class TablesObj(basicobj.SqObject):

    def get(self, **kwargs):
        """Show the tables for which we have information"""
        if self.columns != ["default"]:
            df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with table']})
            return df

        tables = self.engine.get_tables(self.ctxt.cfg, **kwargs)
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
                info.update(table_obj.get_table_info(table, **kwargs))
                tables[i] = info

            if unknown_tables:
                # These are tables for which we don't have processing modules
                # Remove them from the list
                # TODO: Log a warning about these ignored tables
                tables = [x for x in tables if x not in unknown_tables]

            df = pd.DataFrame.from_dict(tables)
            df = df.sort_values(by=['table']).reset_index(drop=True)
            cols = df.columns
            total = pd.DataFrame([['TOTAL',  df['first_time'].min(), df['latest_time'].max(),
                                   df['intervals'].max(),
                                   df['all rows'].sum(), df['namespaces'].max(), df['devices'].max()]],
                                 columns=cols)
            df = df.append(total, ignore_index=True)
        return df

    def describe(self, **kwargs):
        """Describes the fields for a given table"""

        table = kwargs.get('table', '')
        try:
            sch = SchemaForTable(table, self.schemas)
        except ValueError:
            sch = None
        if not sch:
            df = pd.DataFrame(
                {'error': [f'ERROR: incorrect table name {table}']})
            return df

        entries = [{'name': x['name'], 'type': x['type'], 'key': x.get('key', ''),
                    'display': x.get('display', '')}
                   for x in sch.get_raw_schema()]
        df = pd.DataFrame.from_dict(entries).sort_values('name')

        return df

    def summarize(self, **kwargs):
        raise NotImplementedError
