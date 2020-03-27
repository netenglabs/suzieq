import pandas as pd
import pyarrow as pa
from suzieq.utils import SchemaForTable


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

    def system_df(self, namespace) -> pd.DataFrame:
        """Return cached version if present, else add to cache the system DF"""

        if not self.ctxt.engine:
            print("Specify an analysis engine using set engine command")
            return pd.DataFrame(columns=["namespace", "hostname"])

        sys_cols = ["namespace", "hostname", "timestamp"]
        sys_sort = ["namespace", "hostname"]

        # Handle the case we need to fetch the data
        get_data_dc_list = []
        for dc in namespace:
            if self.ctxt.system_df.get(dc, None) is None:
                get_data_dc_list.append(dc)

        if not namespace or get_data_dc_list:
            system_df = self.ctxt.engine.get_table_df(
                self.cfg,
                self.schemas,
                table="system",
                view=self.iobj.view,
                start_time=self.iobj.start_time,
                end_time=self.iobj.end_time,
                namespace=get_data_dc_list,
                sort_fields=sys_sort,
                columns=sys_cols,
            )
            if not get_data_dc_list and not system_df.empty:
                get_data_dc_list = system_df['namespace'].unique()

            for dc in get_data_dc_list:
                if dc not in self.ctxt.system_df:
                    self.ctxt.system_df[dc] = None

                self.ctxt.system_df[dc] = system_df \
                         .query('namespace=="{}"'.format(dc))

            return system_df

        system_df_list = []
        for dc in namespace:
            system_df_list.append(
                self.ctxt.system_df.get(dc, pd.DataFrame(columns=sys_cols)))

        if system_df_list:
            return pd.concat(system_df_list)
        else:
            return pd.DataFrame(columns=sys_cols)

    def get_valid_df(self, table, sort_fields, **kwargs) -> pd.DataFrame:
        if not self.ctxt.engine:
            print("Specify an analysis engine using set engine command")
            return pd.DataFrame(columns=["namespace", "hostname"])

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

        namespace = kwargs.get("namespace", None)
        if not namespace:
            namespace = self.ctxt.namespace

        if not namespace:
            namespace = []

        if table_df.empty:
            return table_df

        if table != "system":
            # This merge is required to ensure that we don't serve out
            # stale data that was obtained before the current run of
            # the agent or from before the system came up
            # We need the system DF cached to avoid slowdown in serving
            # data.
            # TODO: Find a way to invalidate the system df cache.

            drop_cols = ["timestamp_y"]

            if self.iobj.start_time or self.iobj.end_time:
                sys_cols = ["namespace", "hostname", "timestamp"]
                sys_sort = ["namespace", "hostname"]
                sys_df = self.ctxt.engine.get_table_df(
                    self.cfg,
                    self.schemas,
                    table="system",
                    view=self.iobj.view,
                    start_time=self.iobj.start_time,
                    end_time=self.iobj.end_time,
                    namespace=namespace,
                    sort_fields=sys_sort,
                    columns=sys_cols,
                )
            else:
                sys_df = self.system_df(namespace)

            if sys_df.empty:
                return sys_df

            key_fields = [f["name"] for f in self.schemas.get(table)
                          if f.get("key", None) is not None]

            final_df = (
                table_df.merge(sys_df, on=["namespace", "hostname"])
                .dropna(how="any", subset=key_fields)
                .query("timestamp_x >= timestamp_y")
                .drop(columns=drop_cols)
                .rename(
                    index=str,
                    columns={
                        "namespace_x": "namespace",
                        "hostname_x": "hostname",
                        "timestamp_x": "timestamp",
                    },
                )
            )
        else:
            final_df = table_df

        return final_df

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

    def summarize(self, namespace='', **kwargs):
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
            self._add_list_or_count_to_summary(col)

        return pd.DataFrame(self.ns).convert_dtypes()

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
        if df.empty:
            return df

        self.summary_df = df
        self.ns = {i: {} for i in df["namespace"].unique()}
        self.nsgrp = df.groupby(by=["namespace"])

    def _post_summarize(self):
        ns_df = pd.DataFrame(self.ns)
        if len(self.summary_row_order) > 0:
            ns_df = ns_df.reindex(self.summary_row_order, axis=0)
        self.ns_df = ns_df

    def _add_field_to_summary(self, field, method='nunique', field_name=None):
        if not field_name:
            field_name = field
        field_per_ns = getattr(self.nsgrp[field], method)()
        {self.ns[i].update({field_name: field_per_ns[i]})
         for i in field_per_ns.keys()}

    def _add_list_or_count_to_summary(self, field, field_name=None):
        """if there are less than 3 unique things, add as a list, otherwise return the count"""
        if not field_name:
            field_name = field

        count_per_ns = self.nsgrp[field].nunique()
        unique_per_ns = self.nsgrp[field].value_counts()
        for n in count_per_ns.keys():
            if count_per_ns[n] <= 3:
                value = unique_per_ns[n].to_dict()
            else:
                value = count_per_ns[n]
            self.ns[n].update({field_name: value})
            
    def _add_stats_to_summary(self, groupby, fieldname):
        """ takes the pandas groupby object and adds min, max, and median to self.ns"""
        med_field = groupby.median()
        max_field = groupby.max()
        min_field = groupby.min()
        {self.ns[i].update({fieldname: []}) for i in self.ns.keys()}
        {self.ns[i][fieldname].append(min_field[i]) for i in min_field.keys()}
        {self.ns[i][fieldname].append(max_field[i]) for i in max_field.keys()}
        {self.ns[i][fieldname].append(med_field[i]) for i in med_field.keys()}

