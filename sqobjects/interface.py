#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys

import pandas as pd
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.utils import get_query_df
from suzieq.sqobjects import basicobj
from suzieq.sqobjects.lldp import lldpObj


class ifObj(basicobj.SQObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         datacenter, columns, context=context)
        self._table = 'interfaces'
        self._sort_fields = ['datacenter', 'hostname', 'ifname']
        self._cat_fields = ['mtu']

    def aver(self, what='mtu-match', **kwargs) -> pd.DataFrame:
        '''Assert that interfaces are in good state'''
        if what == 'mtu-match':
            result_df = self._assert_mtu_match(**kwargs)
        elif what == 'mtu-value':
            result_df = self._assert_mtu_value(**kwargs)

        return result_df

    def _assert_mtu_value(self, **kwargs) -> pd.DataFrame:
        '''Workhorse routine to match MTU value'''
        columns = ['datacenter', 'hostname', 'ifname', 'state', 'mtu',
                   'timestamp']
        sort_fields = ['datacenter', 'hostname', 'ifname']

        if self.engine == 'spark':
            wherestr = (
                " where active == True and abs(mtu - {}) > 40 and ifname != 'lo'"
                .format(kwargs['matchval']))

            if self.datacenter:
                wherestr += " and datacenter == '{}'".format(
                    kwargs.get('datacenter', []))
            if self.hostname:
                wherestr += " and hostname == '{}'".format(
                    kwargs.get('hostname', []))
            if ifname:
                wherestr += " and ifname == '{}'".format(
                    kwargs.get('ifname', []))

            if sort_fields:
                order_by = 'order by {}'.format(', '.join(sort_fields))

            query_str = 'select {} from interfaces {} {}'.format(
                ', '.join(columns), wherestr, order_by)
            query_df = get_query_df(query_str, self.ctxt.cfg,
                                    self.ctxt.schemas, self.start_time,
                                    self.end_time, view='latest')
        else:
            query_df = self.get_valid_df(
                'interfaces', sort_fields,
                hostname=kwargs.get('hostname', []),
                datacenter=kwargs.get('datacenter', []),
                columns=columns,
                ifname=kwargs.get('ifname', [])) \
                           .query('(abs(mtu - {}) > 40) and (ifname != "lo")'
                                  .format(kwargs['matchval']))

        return query_df

    def _assert_mtu_match(self, **kwargs) -> pd.DataFrame:
        '''Workhorse routine that validates MTU match for specified input'''
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
                    kwargs.get('datacenter', []))
            if self.hostname:
                wherestr += " and lldp.hostname == '{}'".format(
                    kwargs.get('hostname', []))
            if kwargs.get('ifname', ''):
                wherestr += " and lldp.ifname == '{}'".format(
                    kwargs.get('ifname', []))

            wherestr += ')'

            q_str = '{} {} order by hostname, ifname'.format(sel_str, wherestr)
            query_df = get_query_df(q_str, self.ctxt.cfg,
                                    self.ctxt.schemas, self.start_time,
                                    self.end_time, view='latest')
        else:
            lldpobj = lldpObj()
            lldp_df = lldpobj.get(**kwargs)

            if lldp_df.empty:
                print('No Valid LLDP info found, Asserting MTU not possible')
                return pd.DataFrame(columns=lldp_cols)

            columns = ['datacenter', 'hostname', 'ifname', 'state', 'mtu',
                       'timestamp']
            if_df = self.get_valid_df('interfaces', self.sort_fields,
                                      hostname=kwargs.get('hostname', []),
                                      datacenter=kwargs.get('datacenter', []),
                                      columns=columns,
                                      ifname=kwargs.get('ifname', []))
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


if __name__ == '__main__':
    try:
        import fire
        fire.Fire(ifObj)
    except ImportError:
        pass




