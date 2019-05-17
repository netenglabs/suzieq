#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import typing
from ipaddress import ip_interface, ip_network
import pandas as pd

from suzieq.sqobjects import basicobj


class addrObj(basicobj.SQObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         datacenter, columns, context=context)
        self._table = 'interfaces'
        self._sort_fields = ['datacenter', 'hostname', 'ifname']
        self._cat_fields = []

    def _addr_cmp(*addrlist, addr='', match='subnet'):
        ipa = ip_interface(addr)
        for ele in addrlist[1]:
            if (match == 'subnet' and ipa in ip_network(ele, strict=False)):
                return True
            elif (match == 'exact' and ipa.ip == ip_interface(ele).ip):
                return True
        return False

    def get(self, **kwargs):
        if not self._table:
            raise NotImplementedError

        addr = kwargs.get('address', None)
        if addr:
            del kwargs['address']

        match = kwargs.get('match', None)
        if match:
            del kwargs['match']
        else:
            match = 'subnet'
        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self._sort_fields

        df = self.get_valid_df(self._table, sort_fields, **kwargs)
        if ':' in addr:
            return(df[df.ip6AddressList.apply(lambda x: addr in x)])
        else:
            return(df[df.ipAddressList.apply(self._addr_cmp, addr=addr,
                                             match=match)])


if __name__ == '__main__':
    try:
        import fire
        fire.Fire(addressObj)
    except ImportError:
        pass
        pass
