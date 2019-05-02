#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
import json
try:
    from nubia import context
except ImportError:
    pass

import typing
import pandas as pd

sys.path.append('/home/ddutt/work/')
from suzieq.utils import load_sq_config, get_schemas
from suzieq.utils import get_table_df, get_query_df


class SQContext(object):

    cfg = load_sq_config(validate=False)

    schemas = get_schemas(cfg['schema-directory'])

    datacenter = ''
    hostname = ''
    start_time = ''
    end_time = ''
    exec_time = ''
    engine = 'pandas'
    system_df = {}
    sort_fields = []


class SQObject(object):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default']) -> None:

        if 'nubia.internal.context' not in sys.modules:
            self.ctxt = SQContext()
        else:
            self.ctxt = context.get_context()
            if not self.ctxt:
                self.ctxt = SQContext()

        self._ctxt = None
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
    def schemas(self):
        return self.ctxt.schemas

    @property
    def cfg(self):
        return self._cfg

    def system_df(self, datacenter):
        '''Return cached version if present, else add to cache the system DF'''

        sys_cols = ['datacenter', 'hostname', 'timestamp']
        if self.ctxt.system_df.get(datacenter, None) is None:
            sys_cols = ['datacenter', 'hostname', 'timestamp']
            sys_sort = ['datacenter', 'hostname']

            system_df = get_table_df('system', self.start_time, self.end_time,
                                     self.view, sys_sort, self.cfg,
                                     self.schemas, self.engine,
                                     datacenter=datacenter,
                                     columns=sys_cols)
            if datacenter not in self.ctxt.system_df:
                self.ctxt.system_df[datacenter] = None

            self.ctxt.system_df[datacenter] = system_df

        return self.ctxt.system_df.get(datacenter,
                                       pd.DataFrame(columns=sys_cols))

    def get_valid_df(self, table, sort_fields, **kwargs):
        table_df = get_table_df(table, self.start_time, self.end_time,
                                self.view, sort_fields, self.cfg,
                                self.schemas, self.engine, **kwargs)

        datacenter = kwargs.get('datacenter', None)
        if not datacenter:
            datacenter = self.datacenter

        if not datacenter:
            datacenter = 'default'

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

            if self.start_time or self.end_time:
                sys_cols = ['datacenter', 'hostname', 'timestamp']
                sys_sort = ['datacenter', 'hostname']
                sys_df = get_table_df('system', self.start_time,
                                      self.end_time, self.view, sys_sort,
                                      self.cfg, self.schemas, self.engine,
                                      datacenter=datacenter,
                                      columns=sys_cols)
            else:
                sys_df = self.system_df(datacenter[0])

            if sys_df.empty:
                return sys_df

            final_df = table_df.merge(sys_df,
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

    def get(self, **kwargs):
        raise NotImplementedError

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def describe(self, **kwargs):
        raise NotImplementedError

    def summary(self, **kwargs):
        raise NotImplementedError
    
