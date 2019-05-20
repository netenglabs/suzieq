#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import typing
import pandas as pd

from suzieq.utils import load_sq_config, get_schemas
from suzieq.engines import get_sqengine


class SQContext(object):

    def __init__(engine):
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
        engine = get_sqengine(engine)
        if not engine:
            # We really should define our own error
            raise ValueError


class SQObject(object):

    def __init__(self, engine_name: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None, table: str = '') -> None:

        if context is None:
            self.ctxt = SQContext(engine)
        else:
            self.ctxt = context
            if not self.ctxt:
                self.ctxt = SQContext(engine)

        self._cfg = self.ctxt.cfg
        self._schemas = self.ctxt.schemas
        self._table = table
        self._sort_fields = []
        self._cat_fields = []

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

        if engine_name:
            self.engine = get_sqengine(engine_name)
        else:
            self.engine = self.ctxt.engine

        if table:
            self.engine_obj = self.engine.get_object(self._table, self)
        else:
            self.engine_obj = None

    @property
    def schemas(self):
        return self.ctxt.schemas

    @property
    def cfg(self):
        return self._cfg

    def system_df(self, datacenter):
        '''Return cached version if present, else add to cache the system DF'''

        if not self.ctxt.engine:
            print('Specify an analysis engine using set engine command')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        return self.engine_obj.system_df(datacenter,
                                         pd.DataFrame(columns=sys_cols))

    def get_valid_df(self, table, sort_fields, **kwargs):
        if not self.ctxt.engine:
            print('Specify an analysis engine using set engine command')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        return self.engine_obj.get_valid_df(self._table, sort_fields,
                                            **kwargs)
        return(final_df)

    def get(self, **kwargs):
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            print('Specify an analysis engine using set engine command')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self._sort_fields

        return self.engine_obj.get(self._table, sort_fields,
                                   **kwargs)

    def summarize(self, **kwargs):
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            print('Specify an analysis engine using set engine command')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self._sort_fields

        return self.engine_obj.summarize(self._table, sort_fields, **kwargs)

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def top(self, **kwargs):
        raise NotImplementedError



