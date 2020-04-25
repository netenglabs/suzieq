import pandas as pd
import numpy as np
import pyarrow as pa
from suzieq.utils import SchemaForTable
from dateutil.parser import parse, ParserError


class SqEngineObject(object):
    def __init__(self, baseobj):
        self.ctxt = baseobj.ctxt
        self.iobj = baseobj
        self.summary_row_order = []
        self._summarize_on_add_field = []
        self._summarize_on_add_with_query = []
        self._summarize_on_add_list_or_count = []
        self._summarize_on_add_stat = []
        self._summarize_on_perhost_stat = []

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

        self._gen_summarize_data()
        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def _gen_summarize_data(self):
        """Generate the data required for summary"""

        for field_name, col, function in self._summarize_on_add_field:
            if col != 'namespace' and col != 'timestamp':
                self._add_field_to_summary(col, function, field_name)
                self.summary_row_order.append(field_name)

        for field_name, query_str, field in self._summarize_on_add_with_query:
            fld_per_ns = self.summary_df.query(query_str) \
                                        .groupby(by=['namespace'])[field] \
                                        .count()
            for i in self.ns.keys():
                self.ns[i].update({field_name: fld_per_ns[i]})
            self.summary_row_order.append(field_name)

        for field_name, field in self._summarize_on_add_list_or_count:
            self._add_list_or_count_to_summary(field, field_name)
            self.summary_row_order.append(field_name)

        for field_name, query_str, field in self._summarize_on_add_stat:
            if query_str:
                statfld = self.summary_df.query(query_str) \
                                         .groupby(by=['namespace'])[field]
            else:
                statfld = self.summary_df.groupby(by=['namespace'])[field]

            self._add_stats_to_summary(statfld, field_name)
            self.summary_row_order.append(field_name)

        for field_name, query_str, field, func in \
                self._summarize_on_perhost_stat:
            if query_str:
                statfld = self.summary_df \
                              .query(query_str) \
                              .groupby(by=['namespace', 'hostname'])[field] \
                              .agg(func)
            else:
                statfld = self.summary_df \
                              .groupby(by=['namespace', 'hostname'])[field] \
                              .agg(func)

            self._add_stats_to_summary(statfld, field_name, filter_by_ns=True)
            self.summary_row_order.append(field_name)

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

        df = self.get(columns=getcols, **kwargs)
        if df.empty:
            return df

        # check if column we're looking at is a list, and if so explode it
        if df.apply(lambda x: isinstance(x[column], np.ndarray), axis=1).all():
            df = df.explode(column).dropna(how='any')

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
                    .rename(columns={column: 'count',
                                     'index': column})
                    .sort_values('count'))

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def top(self, **kwargs):
        raise NotImplementedError

    def _init_summarize(self, table, **kwargs):
        kwargs.pop('columns', None)
        columns = ['*']
        df = self.get(columns=columns, **kwargs)
        self.summary_df = df
        if df.empty:
            return df

        self.ns = {i: {} for i in df['namespace'].unique()}
        self.nsgrp = df.groupby(by=["namespace"])

    def _post_summarize(self, check_empty_col='deviceCnt'):
        # this is needed in the case that there is a namespace that has no
        # data for this command

        if not check_empty_col:
            check_empty_col = self._check_empty_col

        delete_keys = []
        for ns in self.ns:
            if self.ns[ns][check_empty_col] == 0:
                delete_keys.append(ns)
        for ns in delete_keys:
            del(self.ns[ns])

        ns_df = pd.DataFrame(self.ns)
        if len(self.summary_row_order) > 0:
            ns_df = ns_df.reindex(self.summary_row_order, axis=0)
        self.ns_df = ns_df

    def _add_constant_to_summary(self, field, value):
        """And a constant value to specified field name in summary"""
        if field:
            {self.ns[i].update({field: value}) for i in self.ns.keys()}

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

    def _add_stats_to_summary(self, groupedby, fieldname, filter_by_ns=False):
        """ takes the pandas groupby object and adds min, max, and median to self.ns"""

        {self.ns[i].update({fieldname: []}) for i in self.ns.keys()}
        if filter_by_ns:
            {self.ns[i][fieldname].append(groupedby[i].min())
             for i in self.ns.keys()}
            {self.ns[i][fieldname].append(groupedby[i].max())
             for i in self.ns.keys()}
            {self.ns[i][fieldname].append(groupedby[i].median(numeric_only=False))
             for i in self.ns.keys()}
        else:
            min_field = groupedby.min()
            max_field = groupedby.max()
            med_field = groupedby.median(numeric_only=False)

            {self.ns[i][fieldname].append(min_field[i])
             for i in self.ns.keys()}
            {self.ns[i][fieldname].append(max_field[i])
             for i in self.ns.keys()}
            {self.ns[i][fieldname].append(med_field[i])
             for i in self.ns.keys()}
