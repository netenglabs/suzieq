import pandas as pd
from importlib import import_module

from suzieq.sqobjects import basicobj
from suzieq.utils import SchemaForTable


class TablesObj(basicobj.SqObject):

    def get(self, **kwargs):
        """Show the tables for which we have information"""
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

    def summarize(self, **kwargs):
        """Describes the fields for a given table"""

        df = None
        table = kwargs.get('table', '')
        sch = SchemaForTable(table, self.schemas)

        entries = [{'name': x['name'], 'type': x['type'], 'key': x.get('key', ''), 'display': x.get('display', '')}
                   for x in sch.get_raw_schema()]
        df = pd.DataFrame.from_dict(entries)

        return df
