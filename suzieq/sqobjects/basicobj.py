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


class SqContext(object):

    def __init__(self, engine):
        self.cfg = load_sq_config(validate=False)

        self.schemas = get_schemas(self.cfg['schema-directory'])

        self.datacenter = ''
        self.hostname = ''
        self.start_time = ''
        self.end_time = ''
        self.exec_time = ''
        self.engine = 'pandas'
        self.system_df = {}
        self.sort_fields = []
        self.engine = get_sqengine(engine)
        if not self.engine:
            # We really should define our own error
            raise ValueError


class SqObject(object):

    def __init__(self, engine_name: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None, table: str = '') -> None:

        if context is None:
            self.ctxt = SqContext(engine_name)
        else:
            self.ctxt = context
            if not self.ctxt:
                self.ctxt = SqContext(engine_name)

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

        if self._table:
            self.engine_obj = self.engine.get_object(self._table, self)
        else:
            self.engine_obj = None

    @property
    def schemas(self):
        return self.ctxt.schemas

    @property
    def cfg(self):
        return self._cfg

    def system_df(self, datacenter) -> pd.DataFrame:
        '''Return cached version if present, else add to cache the system DF'''

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        return self.engine_obj.system_df(datacenter,
                                         pd.DataFrame(columns=sys_cols))

    def get_valid_df(self, table, sort_fields, **kwargs) -> pd.DataFrame:
        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        return self.engine_obj.get_valid_df(self._table, sort_fields,
                                            **kwargs)

    def get(self, **kwargs) -> pd.DataFrame:
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        return self.engine_obj.get(**kwargs)

    def summarize(self, **kwargs) -> pd.DataFrame:
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')
            return(pd.DataFrame(columns=['datacenter', 'hostname']))

        return self.engine_obj.summarize(**kwargs)

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def top(self, **kwargs):
        raise NotImplementedError


