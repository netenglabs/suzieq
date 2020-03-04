#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

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
        all_time_df = self._get_table_info(table, view='all')
        default_df = all_time_df.drop_duplicates(subset=key_fields, keep='last')
        times = all_time_df['timestamp'].unique()
        ret = {}
        ret['first_time'] = all_time_df.timestamp.min()
        ret['latest_time'] = all_time_df.timestamp.max()
        ret['intervals'] = len(times)

        ret['latest rows'] = len(default_df)
        ret['all rows'] = len(all_time_df)
        ret['datacenters'] = self._unique_or_zero(default_df, 'datacenter')
        ret['devices'] = self._unique_or_zero(default_df, 'hostname')
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
            ** kwargs
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

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def top(self, **kwargs):
        raise NotImplementedError
