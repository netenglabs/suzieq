#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#


import re
import sys
from pathlib import Path
import json
from collections import OrderedDict
import time

import pandas as pd
from termcolor import cprint
from nubia import command, argument, context
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.utils import get_table_df, get_query_df
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
            query_df = self._assert_mtu_value(ifname, value)
        else:
            query_df = self._assert_mtu_match(ifname)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        if query_df.empty:
            print('Assert passed')
        else:
            print(query_df)
            print('Assert failed')

        return

    @command('ospf')
    @argument("ifname", description="interface name to check OSPF for")
    @argument("vrf", description="VRF to assert OSPF state in")
    def assert_ospf(self, ifname: typing.List[str] = None,
                    vrf: typing.List[str] = None) -> pd.DataFrame:
        """
        Assert OSPF state is good
        """
        pass

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
            query_df = get_table_df(
                'interfaces', self.start_time, self.end_time, self.view,
                sort_fields, self.cfg, self.schemas, self.engine,
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
                "l1.mtu as mtu, peerHostname, peerIfname, l2.mtu as peerMtu "
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
            lldp_df = get_table_df('lldp', self.start_time,
                                   self.end_time,
                                   self.view, sort_fields, self.cfg,
                                   self.schemas, self.engine,
                                   hostname=self.hostname,
                                   datacenter=self.datacenter,
                                   columns=lldp_cols,
                                   ifname=ifname)
            if lldp_df.empty:
                print('No Valid LLDP info found, Asserting MTU not possible')
                return

            columns = ['datacenter', 'hostname', 'ifname', 'state', 'mtu',
                       'timestamp']
            if_df = get_table_df('interfaces', self.start_time,
                                 self.end_time,
                                 self.view, sort_fields, self.cfg,
                                 self.schemas, self.engine,
                                 hostname=self.hostname,
                                 datacenter=self.datacenter,
                                 columns=columns,
                                 ifname=ifname)
            if if_df.empty:
                print('No Valid LLDP info found, Asserting MTU not possible')
                return

            # Now create a single DF where you get the MTU for the lldp
            # combo of (datacenter, hostname, ifname) and the MTU for
            # the combo of (datacenter, peerHostname, peerIfname) and then
            # pare down the result to the rows where the two MTUs don't match
            query_df = pd.merge(lldp_df, if_df, on=['datacenter', 'hostname',
                                                    'ifname'],
                                how='outer') \
                         .dropna(how='any') \
                         .merge(if_df,
                                left_on=['datacenter', 'peerHostname',
                                         'peerIfname'],
                                right_on=['datacenter', 'hostname', 'ifname'],
                                how='outer') \
                         .dropna(how='any') \
                         .query('mtu_x != mtu_y') \
                         .drop(columns=['timestamp_x', 'timestamp_y', 'hostname_y',
                                        'ifname_y', 'state_x', 'state_y']) \
                         .rename(index=str, columns={'hostname_x': 'hostname',
                                                     'ifname_x': 'ifname',
                                                     'mtu_x': 'mtu',
                                                     'mtu_y': 'peerMtu'})

        return query_df

    def _assert_ospf(self, query_str, ospf_df, if_df):
        '''Workhorse routine to assert OSPF state'''
        pass



