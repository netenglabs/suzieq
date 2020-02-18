#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

from ipaddress import IPv4Network
import typing
import pandas as pd

from suzieq.sqobjects import basicobj


class OspfObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         datacenter, columns, context=context, table='ospf')
        self._sort_fields = ['datacenter', 'hostname', 'vrf', 'ifname']
        self._cat_fields = []

    def get(self, **kwargs):

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.get(**kwargs)

    def summarize(self, **kwargs):
        """Describe the data"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.summarize(**kwargs)

    def aver(self, **kwargs):
        """Assert that the OSPF state is OK"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.aver(**kwargs)

    def top(self, what='transitions', n=5, **kwargs) -> pd.DataFrame:
        """Get the list of top stuff about OSPF"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.top(what=what, n=n, **kwargs)


if __name__ == '__main__':
    pass
