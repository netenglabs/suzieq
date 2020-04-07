import pandas as pd
import pyarrow as pa
from suzieq.utils import SchemaForTable
from dateutil.parser import parse, ParserError


class SqEngineObject(object):
    def __init__(self, baseobj):
        self.ctxt = baseobj.ctxt
        self.iobj = baseobj
        self.summary_row_order = []

    @property
    def schemas(self):
        return self.ctxt.schemas

    @property
    def cfg(self):
        return self.iobj._cfg

    @property
    def table(self):
        return self.iobj._table

    @property
    def sort_fields(self):
        return self.iobj._sort_fields

    def get_valid_df(self, table, sort_fields, **kwargs) -> pd.DataFrame:
        if not self.ctxt.engine:
            print("Specify an analysis engine using set engine command")
            return pd.DataFrame(columns=["namespace", "hostname"])

        for dt in [self.iobj.start_time, self.iobj.end_time]:
            if dt:
                try:
                    parse(dt)
                except (ValueError, ParserError) as e:
                    print(f"invalid time {dt}: {e}")
                    return pd.DataFrame()

        table_df = self.ctxt.engine.get_table_df(
            self.cfg,
            self.schemas,
            table=table,
            view=self.iobj.view,
            start_time=self.iobj.start_time,
            end_time=self.iobj.end_time,
            sort_fields=sort_fields,
            **kwargs
        )

        return table_df

    def get(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        try:
            df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs)
        except pa.lib.ArrowInvalid:
            return(pd.DataFrame(columns=['namespace', 'hostname']))

        return df

    def get_table_info(self, table, **kwargs):
        sch = SchemaForTable(table, schema=self.schemas)
        key_fields = sch.key_fields()
        # You can't use view from user because we need to see all the data
        # to compute data required.
        kwargs.pop('view', None)
        all_time_df = self._get_table_info(table, view='all', **kwargs)
        times = all_time_df['timestamp'].unique()
        ret = {'first_time': all_time_df.timestamp.min(),
               'latest_time': all_time_df.timestamp.max(),
               'intervals': len(times),
               'all rows': len(all_time_df),
               'namespaces': self._unique_or_zero(all_time_df, 'namespace'),
               'devices': self._unique_or_zero(all_time_df, 'hostname')}

        return ret

    def _unique_or_zero(self, df, col):
        if col in df.columns:
            return len(df[col].unique())
        else:
            return 0

    def _get_table_info(self, table, view='latest', **kwargs):
        df = self.ctxt.engine.get_table_df(
            self.cfg,
            self.schemas,
            table=table,
            view=view,
            start_time='',
            end_time='',
            sort_fields=None,
            **kwargs
        )
        return df

    def summarize(self, **kwargs):
        """There is a pattern of how to do these
        use self._init_summarize(), 
            creates self.summary_df, which is the initial pandas dataframe based on the table
            creates self.nsgrp of data grouped by namespace
            self.ns is the dict to add data to which will be turned into a dataframe and then returned

        if you want to simply take a field and run a pandas functon, then use
          self._add_field_to_summary

        at the end of te summarize
        return pd.DataFrame(self.ns).convert_dtypes()

        If you don't override this, then you get a default summary of all columns
        """
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        for col in self.summary_df.columns:
            if col != 'namespace' and col != 'timestamp':
                self._add_list_or_count_to_summary(col)
        self._add_field_to_summary('hostname', 'count', 'rows')

        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def unique(self, **kwargs) -> pd.DataFrame:
        """Return the unique elements as per user specification"""
        groupby = kwargs.pop("groupby", None)

        columns = kwargs.pop("columns", None)
        if columns is None or columns == ['default']:
            raise ValueError('Must specify columns with unique')

        if len(columns) > 1:
            raise ValueError('Specify a single column with unique')

        if groupby:
            getcols = columns + groupby.split()
        else:
            getcols = columns

        column = columns[0]

        type = kwargs.pop('type', 'entry')

        df = self.get_valid_df(self.iobj._table, self.iobj._sort_fields,
                               columns=getcols, **kwargs)
        if df.empty:
            return df

        if groupby:
            if type == 'host' and 'hostname' not in groupby:
                grp = df.groupby(by=groupby.split() + ['hostname', column])
                grpkeys = list(grp.groups.keys())
                gdict = {}
                for i, g in enumerate(groupby.split() + ['hostname', column]):
                    gdict[g] = [x[i] for x in grpkeys]
                r = pd.DataFrame(gdict).groupby(by=groupby.split())[column] \
                                       .value_counts()
                return (pd.DataFrame({'count': r})
                          .reset_index())

            else:
                r = df.groupby(by=groupby.split())[column].value_counts()
                return pd.DataFrame({'count': r}).reset_index()
        else:
            if type == 'host' and column != 'hostname':
                r = df.groupby('hostname').first()[column].value_counts()
            else:
                r = df[column].value_counts()

            return (pd.DataFrame({column: r})
                    .reset_index()
                    .sort_values('index')
                    .rename(columns={column: 'count',
                                     'index': column}))

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def top(self, **kwargs):
        raise NotImplementedError

    def _init_summarize(self, table, **kwargs):
        kwargs.pop('columns', None)
        columns = ['*']
        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields
        df = self.get_valid_df(table, sort_fields, columns=columns, **kwargs)
        self.summary_df = df
        if df.empty:
            return df

        self.ns = {i: {} for i in df['namespace'].unique()}
        self.nsgrp = df.groupby(by=["namespace"])

    def _post_summarize(self):
        # this is needed in the case that there is a namespace that has no
        # data for this command
        delete_keys = []
        for ns in self.ns:
            if self.ns[ns]['rows'] == 0:
                delete_keys.append(ns)
        for ns in delete_keys:
            del(self.ns[ns])

        ns_df = pd.DataFrame(self.ns)
        if len(self.summary_row_order) > 0:
            ns_df = ns_df.reindex(self.summary_row_order, axis=0)
        self.ns_df = ns_df

    def _add_field_to_summary(self, field, method='nunique', field_name=None):
        if not field_name:
            field_name = field
        field_per_ns = getattr(self.nsgrp[field], method)()
        {self.ns[i].update({field_name: field_per_ns[i]})
         for i in self.ns.keys()}

    def _add_list_or_count_to_summary(self, field, field_name=None):
        """if there are less than 3 unique things, add as a list, otherwise return the count"""
        if not field_name:
            field_name = field

        count_per_ns = self.nsgrp[field].nunique()

        for n in self.ns.keys():
            if 3 >= count_per_ns[n] > 0:
                # can't do a value_counts on all groups, incase one of the groups other groups doesn't have data
                unique_for_ns = self.nsgrp.get_group(n)[field].value_counts()
                value = unique_for_ns.to_dict()

            else:
                value = count_per_ns[n]

            self.ns[n].update({field_name: value})

    def _add_stats_to_summary(self, groupby, fieldname):
        """ takes the pandas groupby object and adds min, max, and median to self.ns"""
        med_field = groupby.median()
        max_field = groupby.max()
        min_field = groupby.min()
        {self.ns[i].update({fieldname: []}) for i in self.ns.keys()}
        {self.ns[i][fieldname].append(min_field[i]) for i in self.ns.keys()}
        {self.ns[i][fieldname].append(max_field[i]) for i in self.ns.keys()}
        {self.ns[i][fieldname].append(med_field[i]) for i in self.ns.keys()}
