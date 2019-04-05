#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#


import sys
import json
import time
from ipaddress import IPv4Network

import pandas as pd
from termcolor import cprint
from nubia import command, argument, context
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.utils import get_query_df
from suzieq.cli.commands.command import SQCommand


@command('assert', help="assert network state")
class AssertCommand(SQCommand):
    '''Assert Commands'''

    @command('mtu')
    @argument("ifname", description="Name of interface to check MTU for")
    @argument("what", description="What do you want to assert about MTU",
              choices=['match', 'value'])
    @argument("value", description="Value of MTU to match")
    def assert_mtu(self, ifname: typing.List[str] = None,
                   vrf: typing.List[str] = None,
                   what: str = 'match', value: int = 0):
        """
        Assert MTU matches
        """
        now = time.time()
        if what == 'value':
            result_df = self._assert_mtu_value(ifname, value)
        else:
            result_df = self._assert_mtu_match(ifname)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        if result_df.empty:
            print('Assert passed')
        else:
            print(result_df)
            print('Assert failed')

        return

    @command('ospf')
    @argument("ifname", description="interface name to check OSPF for")
    @argument("vrf", description="VRF to assert OSPF state in")
    @argument("what", description="What do you want to assert about OSPF",
              choices=['all'])
    def assert_ospf(self, ifname: typing.List[str] = None,
                    vrf: typing.List[str] = None,
                    what: str = 'all') -> pd.DataFrame:
        """
        Assert OSPF state is good
        """
        now = time.time()
        result_df = self._assert_ospf(ifname, vrf, what)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        if result_df.empty:
            print('Assert passed')
        else:
            print(result_df)
            print('Assert failed')

        return
        

    def _assert_mtu_value(self, ifname, value):
        '''Workhorse routine to assert that all interfaces have MTU <= value'''
        columns = ['datacenter', 'hostname', 'ifname', 'state', 'mtu',
                   'timestamp']
        sort_fields = ['datacenter', 'hostname', 'ifname']

        if self.engine == 'spark':
            wherestr = (
                " where active == True and abs(mtu - {}) > 40 and ifname != 'lo'"
                .format(value))

            if self.datacenter:
                wherestr += " and datacenter == '{}'".format(
                    self.datacenter)
            if self.hostname:
                wherestr += " and hostname == '{}'".format(self.hostname)
            if ifname:
                wherestr += " and ifname == '{}'".format(self.ifname)

            if sort_fields:
                order_by = 'order by {}'.format(', '.join(sort_fields))

            query_str = 'select {} from interfaces {} {}'.format(
                ', '.join(columns), wherestr, order_by)
            query_df = get_query_df(query_str, self.ctxt.cfg,
                                    self.ctxt.schemas, self.start_time,
                                    self.end_time, view='latest')
        else:
            # Now for Pandas
            query_df = self.get_valid_df(
                'interfaces', sort_fields, 
                hostname=self.hostname, datacenter=self.datacenter,
                columns=columns, ifname=ifname) \
                .query('(abs(mtu - {}) > 40) and (ifname != "lo")'
                       .format(value))

        return query_df

    def _assert_mtu_match(self, ifname) -> pd.DataFrame:
        '''Workhorse routine to assert no MTU mismatch'''
        if self.engine == 'spark':
            sel_str = (
                "select lldp.datacenter as datacenter, "
                "lldp.hostname as hostname, lldp.ifname as ifname, "
                "peerHostname, peerIfname, l1.mtu as mtu, l2.mtu as peerMtu "
                "from lldp"
                )
            wherestr = (
                "inner join interfaces as l1 inner join interfaces as l2 on "
                "(l1.mtu != l2.mtu and "
                "(l1.active==True and l2.active==True) and "
                "(l1.hostname == lldp.hostname and "
                "l1.ifname == lldp.ifname) and "
                "(l2.hostname == peerHostname and  l2.ifname == peerIfname) "
                "and (l1.datacenter == l2.datacenter)"
            )

            if self.datacenter:
                wherestr += " and lldp.datacenter == '{}'".format(
                    self.datacenter)
            if self.hostname:
                wherestr += " and lldp.hostname == '{}'".format(self.hostname)
            if ifname:
                wherestr += " and lldp.ifname == '{}'".format(self.ifname)

            wherestr += ')'

            q_str = '{} {} order by hostname, ifname'.format(sel_str, wherestr)
            query_df = get_query_df(q_str, self.ctxt.cfg,
                                    self.ctxt.schemas, self.start_time,
                                    self.end_time, view='latest')
        else:
            # Get LLDP table and the Interfaces table
            lldp_cols = ['datacenter', 'hostname', 'ifname', 'peerHostname',
                         'peerIfname', 'timestamp']
            sort_fields = ['datacenter', 'hostname', 'ifname']
            lldp_df = self.get_valid_df('lldp', sort_fields, 
                                        hostname=self.hostname,
                                        datacenter=self.datacenter,
                                        columns=lldp_cols,
                                        ifname=ifname)
            if lldp_df.empty:
                print('No Valid LLDP info found, Asserting MTU not possible')
                return pd.DataFrame(columns=lldp_cols)

            columns = ['datacenter', 'hostname', 'ifname', 'state', 'mtu',
                       'timestamp']
            if_df = self.get_valid_df('interfaces', sort_fields,
                                      hostname=self.hostname,
                                      datacenter=self.datacenter,
                                      columns=columns,
                                      ifname=ifname)
            if if_df.empty:
                print('No Valid LLDP info found, Asserting MTU not possible')
                return pd.DataFrame(columns=columns)

            # Now create a single DF where you get the MTU for the lldp
            # combo of (datacenter, hostname, ifname) and the MTU for
            # the combo of (datacenter, peerHostname, peerIfname) and then
            # pare down the result to the rows where the two MTUs don't match
            query_df = pd.merge(lldp_df, if_df[['datacenter', 'hostname',
                                                'ifname', 'mtu']],
                                on=['datacenter', 'hostname', 'ifname'],
                                how='outer') \
                         .dropna(how='any') \
                         .merge(if_df[['datacenter', 'hostname', 'ifname',
                                       'mtu']],
                                left_on=['datacenter', 'peerHostname',
                                         'peerIfname'],
                                right_on=['datacenter', 'hostname', 'ifname'],
                                how='outer') \
                         .dropna(how='any') \
                         .query('mtu_x != mtu_y') \
                         .drop(columns=['hostname_y', 'ifname_y']) \
                         .rename(index=str, columns={'hostname_x': 'hostname',
                                                     'ifname_x': 'ifname',
                                                     'mtu_x': 'mtu',
                                                     'mtu_y': 'peerMtu'})

        return query_df

    def _assert_ospf(self, ifname: str, vrf: str, what: str):
        '''Workhorse routine to assert OSPF state'''

        columns = ['datacenter', 'hostname', 'vrf', 'ifname', 'routerId',
                   'helloTime', 'deadTime', 'passive', 'ipAddress',
                   'networkType', 'timestamp', 'area', 'nbrCount']
        sort_fields = ['datacenter', 'hostname', 'ifname', 'vrf']

        ospf_df = self.get_valid_df('ospfIf', sort_fields,
                                    hostname=self.hostname,
                                    columns=columns,
                                    datacenter=self.datacenter, ifname=ifname,
                                    vrf=vrf)

        if ospf_df.empty:
            return pd.DataFrame(columns=columns)

        df = ospf_df.groupby(['routerId'], as_index=False)[['hostname']] \
                    .agg(lambda x: x.unique().tolist())

        dup_rtrid_df = df[df['hostname'].map(len) > 1]

        bad_ospf_df = ospf_df.query('nbrCount < 1 and passive != "True"')

        # OK, we do have nodes with zero nbr count. Lets see why
        lldp_cols = ['datacenter', 'hostname', 'ifname', 'peerHostname',
                     'peerIfname', 'timestamp']
        sort_fields = ['datacenter', 'hostname', 'ifname']
        lldp_df = self.get_valid_df('lldp', sort_fields,
                                    hostname=self.hostname,
                                    datacenter=self.datacenter,
                                    columns=lldp_cols, ifname=ifname)
        if lldp_df.empty:
            print('No LLDP info, unable to ascertain cause of OSPF failure')
            return bad_ospf_df

        # Create a single massive DF with fields populated appropriately
        use_cols = ['datacenter', 'routerId', 'hostname', 'vrf', 'ifname',
                    'helloTime', 'deadTime', 'passive', 'ipAddress',
                    'networkType', 'area']
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
                                   if IPv4Network(x['ipAddress_x'],
                                                  strict=False)
                                   != IPv4Network(x['ipAddress_y'],
                                                  strict=False)
                                   else tuple(), axis=1)
        df1['reason'] += df1.apply(lambda x: tuple(['area mismatch'])
                                   if x['area_x'] != x['area_y'] else tuple(),
                                   axis=1)
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


