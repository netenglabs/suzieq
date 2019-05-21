#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import pandas as pd
import typing

from suzieq.sqobjects import basicobj


class ifObj(basicobj.SQObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         datacenter, columns, context=context,
                         table='interfaces')
        self._sort_fields = ['datacenter', 'hostname', 'ifname']
        self._cat_fields = ['mtu']

    def aver(self, what='mtu-match', **kwargs) -> pd.DataFrame:
        '''Assert that interfaces are in good state'''
        return self.engine_obj.aver(what=what, **kwargs)

    def top(self, what='transitions', n=5, **kwargs) -> pd.DataFrame:
        '''Get the list of top link changes'''
        return self.engine_obj.top(what=what, n=n, **kwargs)


if __name__ == '__main__':
    try:
        import fire
        fire.Fire(ifObj)
    except ImportError:
        pass

