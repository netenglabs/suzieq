#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
from ipaddress import IPv4Network
import typing
import pandas as pd

from suzieq.utils import get_query_df, get_display_fields
from suzieq.sqobjects.lldp import lldpObj
from suzieq.sqobjects import basicobj

class ospfObj(basicobj.SQObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         datacenter, columns, context=context)
        self._table = 'ospfNbr'
        self._sort_fields = ['datacenter', 'hostname', 'vrf', 'ifname']
        self._cat_fields = []

    def get(self, **kwargs):

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self._sort_fields

        table = 'ospfNbr'
        if 'type' in kwargs:
            if kwargs.get('type', 'interface') == 'interface':
                table = 'ospfIf'
            del kwargs['type']

        df = self.get_valid_df(table, sort_fields, **kwargs)
        return(df)

    def summarize(self, **kwargs):
        '''Describe the data'''
        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self._sort_fields

        table = 'ospfNbr'
        if 'type' in kwargs:
            if kwargs.get('type', 'interface') == 'interface':
                table = 'ospfIf'
            del kwargs['type']

        df = self.get_valid_df(table, sort_fields, **kwargs)

        if not df.empty:
            if kwargs.get('groupby'):
                return(df
                       .groupby(kwargs['groupby'])
                       .agg(lambda x: x.unique().tolist()))
            else:
                return(df
                       .describe(include='all')
                       .fillna('-'))

    def aver(self, **kwargs):
        '''Assert that the OSPF state is OK'''

        columns = ['datacenter', 'hostname', 'vrf', 'ifname', 'routerId',
                   'helloTime', 'deadTime', 'passive', 'ipAddress',
                   'isUnnumbered', 'areaStub', 'networkType', 'timestamp',
                   'area', 'nbrCount']
        sort_fields = ['datacenter', 'hostname', 'ifname', 'vrf']

        ospf_df = self.get_valid_df('ospfIf', sort_fields, columns=columns,
                                    **kwargs)
        if ospf_df.empty:
            return pd.DataFrame(columns=columns)

        df = ospf_df.ix[ospf_df['routerId'] != ''] \
                    .groupby(['routerId'], as_index=False)[['hostname']] \
                    .agg(lambda x: x.unique().tolist())

        dup_rtrid_df = df[df['hostname'].map(len) > 1]

        bad_ospf_df = ospf_df.query('nbrCount < 1 and passive != "True"')

        lldpobj = lldpObj()
        lldp_df = lldpobj.get(datacenter=kwargs.get('datacenter', ''),
                              hostname=kwargs.get('hostname', ''),
                              ifname=kwargs.get('ifname', ''))
        if lldp_df.empty:
            print('No LLDP info, unable to ascertain cause of OSPF failure')
            return bad_ospf_df

        # Create a single massive DF with fields populated appropriately
        use_cols = ['datacenter', 'routerId', 'hostname', 'vrf', 'ifname',
                    'helloTime', 'deadTime', 'passive', 'ipAddress',
                    'areaStub', 'isUnnumbered', 'networkType', 'area']
        df1 = pd.merge(lldp_df, ospf_df[use_cols],
                       on=['datacenter', 'hostname', 'ifname']) \
                .dropna(how='any') \
                .merge(ospf_df[use_cols], how='outer',
                       left_on=['datacenter', 'peerHostname', 'peerIfname'],
                       right_on=['datacenter', 'hostname', 'ifname']) \
                .dropna(how='any')

        if df1.empty:
            return dup_rtrid_df

        # Now start comparing the various parameters
        df1['reason'] = tuple([tuple() for _ in range(len(df1))])
        df1['reason'] += df1.apply(lambda x: tuple(['subnet mismatch'])
                                   if ((x['isUnnumbered_x'] !=
                                        x['isUnnumbered_y']) and
                                       (IPv4Network(x['ipAddress_x'],
                                                    strict=False)
                                        != IPv4Network(x['ipAddress_y'],
                                                       strict=False)))
                                   else tuple(), axis=1)
        df1['reason'] += df1.apply(lambda x: tuple(['area mismatch'])
                                   if (x['area_x'] != x['area_y'] and
                                       x['areaStub_x'] != x['areaStub_y'])
                                   else tuple(), axis=1)
        df1['reason'] += df1.apply(lambda x: tuple(['Hello timers mismatch'])
                                   if x['helloTime_x'] != x['helloTime_y']
                                   else tuple(), axis=1)
        df1['reason'] += df1.apply(lambda x: tuple(['Dead timer mismatch'])
                                   if x['deadTime_x'] != x['deadTime_y']
                                   else tuple(), axis=1)
        df1['reason'] += df1.apply(lambda x: tuple(['network type mismatch'])
                                   if x['networkType_x'] != x['networkType_y']
                                   else tuple(), axis=1)
        df1['reason'] += df1.apply(lambda x: tuple(['passive config mismatch'])
                                   if x['passive_x'] != x['passive_y']
                                   else tuple(), axis=1)
        df1['reason'] += df1.apply(lambda x: tuple(['vrf mismatch']) if
                                   x['vrf_x'] != x['vrf_y'] else tuple(),
                                   axis=1)

        # Add back the duplicate routerid stuff
        def is_duprtrid(x):
            for p in dup_rtrid_df['hostname'].tolist():
                if x['hostname_x'] in p:
                    x['reason'] = tuple(['duplicate routerId:{}'.format(p)])

            return x

        df2 = df1.apply(is_duprtrid, axis=1) \
                 .drop_duplicates(subset=['datacenter', 'hostname_x'],
                                  keep='last') \
                 .query('reason != tuple()')[['datacenter', 'hostname_x',
                                              'vrf_x', 'reason']]
        df1 = pd.concat([df1, df2], sort=False)
        return (df1.rename(index=str,
                           columns={'hostname_x': 'hostname',
                                    'ifname_x': 'ifname', 'vrf_x': 'vrf'})
                [['datacenter', 'hostname', 'ifname', 'vrf', 'reason']]) \
                .query('reason != tuple()') \
                .fillna('-')

    def top(self, what='transitions', n=5, **kwargs) -> pd.DataFrame:
        '''Get the list of top stuff about OSPF'''

        if 'columns' in kwargs:
            columns = kwargs['columns']
            del kwargs['columns']
        else:
            columns = ['default']

        columns = get_display_fields('ospfNbr', columns,
                                     self.schemas[self._table])
        if 'numChanges' not in columns:
            columns.insert(-2, 'numChanges')

        df = self.get(columns=columns, **kwargs)
        if df.empty:
            return df

        return df.nlargest(n, columns=['numChanges'], keep='all').head(n=n)


if __name__ == '__main__':
    try:
        import fire
        fire.Fire(ospfObj)
    except ImportError:
        pass



