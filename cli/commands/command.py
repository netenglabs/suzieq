
import re
import sys
from pathlib import Path
import json
from collections import OrderedDict


import pandas as pd
from termcolor import cprint
from nubia import command, argument, context
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.utils import get_table_df, get_query_df


class SQCommand:
    '''Base Command Class for use with all verbs'''
    @argument("engine", description="which analytical engine to use",
              choices=['spark', 'pandas'])
    @argument("datacenter", description="datacenter to qualify selection")
    @argument("hostname", description="Name of host to qualify selection")
    @argument("start_time",
              description="Start of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("end_time",
              description="End of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("view", description="view all records or just the latest",
              choices=["all", "latest"])
    @argument("columns", description="columns to extract, [*] for all")
    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default']) -> None:
        self.ctxt = context.get_context()
        self._cfg = self.ctxt.cfg
        self._schemas = self.ctxt.schemas

        if not datacenter and self.ctxt.datacenter:
            self.datacenter = self.ctxt.datacenter
        else:
            self.datacenter = datacenter
        if not hostname and self.ctxt.hostname:
            self.hostname = self.ctxt.hostname
        else:
            self.hostname = hostname

        if not start_time and self.ctxt.start_time:
            self.start_time = self.ctxt.start_time
        else:
            self.start_time = start_time

        if not end_time and self.ctxt.end_time:
            self.end_time = self.ctxt.end_time
        else:
            self.end_time = end_time

        self.view = view
        self.columns = columns

        if engine:
            self.engine = engine
        else:
            self.engine = self.ctxt.engine

    @property
    def cfg(self):
        return self._cfg

    @property
    def schemas(self):
        return self._schemas
    """show various pieces of information"""

    @property
    def system_df(self):
        if self.ctxt.system_df is None:
            sys_cols = ['datacenter', 'hostname', 'timestamp']
            sys_sort = ['datacenter', 'hostname']

            system_df = get_table_df('system', self.start_time, self.end_time,
                                     self.view, sys_sort, self.cfg,
                                     self.schemas, self.engine,
                                     datacenter=self.datacenter,
                                     columns=sys_cols)
            self.ctxt.system_df = system_df

        return self.ctxt.system_df

    def get_valid_df(self, table, sort_fields, **kwargs):
        table_df = get_table_df(table, self.start_time, self.end_time,
                                self.view, sort_fields, self.cfg,
                                self.schemas, self.engine, **kwargs)

        if table_df.empty:
            return table_df

        if table != 'system':
            # This merge is required to ensure that we don't serve out
            # stale data that was obtained before the current run of
            # the agent or from before the system came up
            # We need the system DF cached to avoid slowdown in serving
            # data.
            # TODO: Find a way to invalidate the system df cache.

            drop_cols = ['timestamp_y']

            if self.system_df.empty:
                return self.system_df

            final_df = table_df.merge(self.system_df,
                                      on=['datacenter', 'hostname']) \
                               .dropna(how='any') \
                               .query('timestamp_x >= timestamp_y') \
                               .drop(columns=drop_cols) \
                               .rename(index=str, columns={
                                   'datacenter_x': 'datacenter',
                                   'hostname_x': 'hostname',
                                   'timestamp_x': 'timestamp'})
        else:
            final_df = table_df

        return(final_df)


