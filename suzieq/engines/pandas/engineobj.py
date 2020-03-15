import pandas as pd
import pyarrow as pa
from suzieq.utils import SchemaForTable


class SqEngineObject(object):
    def __init__(self, baseobj):
        self.ctxt = baseobj.ctxt
        self.iobj = baseobj

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

    def system_df(self, datacenter) -> pd.DataFrame:
        """Return cached version if present, else add to cache the system DF"""

        if not self.ctxt.engine:
            print("Specify an analysis engine using set engine command")
            return pd.DataFrame(columns=["datacenter", "hostname"])

        sys_cols = ["datacenter", "hostname", "timestamp"]
        sys_sort = ["datacenter", "hostname"]

        # Handle the case we need to fetch the data
        get_data_dc_list = []
        for dc in datacenter:
            if self.ctxt.system_df.get(dc, None) is None:
                get_data_dc_list.append(dc)

        if not datacenter or get_data_dc_list:
            system_df = self.ctxt.engine.get_table_df(
                self.cfg,
                self.schemas,
                table="system",
                view=self.iobj.view,
                start_time=self.iobj.start_time,
                end_time=self.iobj.end_time,
                datacenter=get_data_dc_list,
                sort_fields=sys_sort,
                columns=sys_cols,
            )
            if not get_data_dc_list and not system_df.empty:
                get_data_dc_list = system_df['datacenter'].unique()

            for dc in get_data_dc_list:
                if dc not in self.ctxt.system_df:
                    self.ctxt.system_df[dc] = None

                self.ctxt.system_df[dc] = system_df \
                         .query('datacenter=="{}"'.format(dc))

            return system_df

        system_df_list = []
        for dc in datacenter:
            system_df_list.append(
                self.ctxt.system_df.get(dc, pd.DataFrame(columns=sys_cols)))

        if system_df_list:
            return pd.concat(system_df_list)
        else:
            return pd.DataFrame(columns=sys_cols)

    def get_valid_df(self, table, sort_fields, **kwargs) -> pd.DataFrame:
        if not self.ctxt.engine:
            print("Specify an analysis engine using set engine command")
            return pd.DataFrame(columns=["datacenter", "hostname"])

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

        datacenter = kwargs.get("datacenter", None)
        if not datacenter:
            datacenter = self.ctxt.datacenter

        if not datacenter:
            datacenter = []

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
                sys_cols = ["datacenter", "hostname", "timestamp"]
                sys_sort = ["datacenter", "hostname"]
                sys_df = self.ctxt.engine.get_table_df(
                    self.cfg,
                    self.schemas,
                    table="system",
                    view=self.iobj.view,
                    start_time=self.iobj.start_time,
                    end_time=self.iobj.end_time,
                    datacenter=datacenter,
                    sort_fields=sys_sort,
                    columns=sys_cols,
                )
            else:
                sys_df = self.system_df(datacenter)

            if sys_df.empty:
                return sys_df

            key_fields = [f["name"] for f in self.schemas.get(table)
                          if f.get("key", None) is not None]

            final_df = (
                table_df.merge(sys_df, on=["datacenter", "hostname"])
                .dropna(how="any", subset=key_fields)
                .query("timestamp_x >= timestamp_y")
                .drop(columns=drop_cols)
                .rename(
                    index=str,
                    columns={
                        "datacenter_x": "datacenter",
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
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        return df

    def get_table_info(self, table, **kwargs):
        sch = SchemaForTable(table, schema=self.schemas)
        key_fields = sch.key_fields()
        # You can't use view from user because we need to see all the data
        # to compute data required.
        kwargs.pop('view', None)
        all_time_df = self._get_table_info(table, view='all', **kwargs)
        default_df = all_time_df.drop_duplicates(
            subset=key_fields, keep='last')
        times = all_time_df['timestamp'].unique()
        ret = {'first_time': all_time_df.timestamp.min(),
               'latest_time': all_time_df.timestamp.max(),
               'intervals': len(times),
               'latest rows': len(default_df),
               'all rows': len(all_time_df),
               'datacenters': self._unique_or_zero(default_df, 'datacenter'),
               'devices': self._unique_or_zero(default_df, 'hostname')}

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
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs)

        if not df.empty:
            if kwargs.get("groupby"):
                return df.groupby(kwargs["groupby"]) \
                         .agg(lambda x: x.unique().tolist())
            else:
                for i in self.iobj._cat_fields:
                    if (kwargs.get(i, []) or
                            "default" in kwargs.get("columns", [])):
                        df[i] = df[i].astype("category", copy=False)
                return df.describe(include="all").fillna("-")

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
