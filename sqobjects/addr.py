#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import typing
from ipaddress import ip_interface, ip_network, IPv4Interface, IPv6Interface
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

    def _addr_cmp(*addrlist: pd.array, addr='',
                  match: str = 'subnet') -> bool:
        for ele in addrlist[1]:
            if (match == 'subnet' and addr in ip_network(ele, strict=False)):
                return True
            elif (match == 'exact' and addr.ip == ip_interface(ele).ip):
                return True
        return False

    def get(self, **kwargs) -> pd.DataFrame:
        '''Retrieve the dataframe that matches a given IP address'''
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

        columns = kwargs.get('columns', [])
        del kwargs['columns']
        if columns != ['default']:
            for col in ['macaddr', 'ip6AddressList', 'ipAddressList']:
                if col not in columns:
                    columns.insert(4, col)
        else:
            columns = ['datacenter', 'hostname', 'ifname', 'ipAddressList',
                       'ip6AddressList', 'macaddr']

        df = self.get_valid_df(self._table, sort_fields, columns=columns,
                               **kwargs)
        try:
            ipa = ip_interface(addr)
            if type(ipa) == IPv6Interface:
                return(df[df.ip6AddressList.apply(self._addr_cmp, addr=ipa,
                                                  match=match)])
            else:
                return(df[df.ipAddressList.apply(self._addr_cmp, addr=ipa,
                                                 match=match)])
        except ValueError:
            # Is this a MAC address?
            return(df[df.macaddr == addr])

    def describe(self, **kwargs):
        '''Describe the IP Address data'''
        pass


if __name__ == '__main__':
    try:
        import fire
        fire.Fire(addrObj)
    except ImportError:
        pass
        pass
