from typing import Callable, List, Tuple, Union
from ipaddress import ip_network
import re
import operator

import numpy as np
import pandas as pd
from ciscoconfparse import CiscoConfParse

from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.shared.confutils import (get_access_port_interfaces,
                                     get_trunk_port_interfaces)
from suzieq.shared.utils import build_query_str


class InterfacesObj(SqPandasEngine):
    '''Backend class to handle manipulating interfaces table with pandas'''

    def __init__(self, baseobj):
        super().__init__(baseobj)
        self._assert_result_cols = ['namespace', 'hostname', 'ifname', 'state',
                                    'peerHostname', 'peerIfname', 'result',
                                    'assertReason', 'timestamp']

    @staticmethod
    def table_name():
        '''Table name'''
        return 'interfaces'

    def get(self, **kwargs):
        """Handling state outside of regular filters"""
        state = kwargs.pop('state', '')
        iftype = kwargs.pop('type', '')
        ifname = kwargs.get('ifname', '')
        vrf = kwargs.pop('vrf', '')
        master = kwargs.pop('master', [])
        columns = kwargs.pop('columns', [])
        user_query = kwargs.pop('query_str', '')
        vlan = kwargs.pop('vlan', '')
        portmode = kwargs.pop('portmode', '')

        addnl_fields = []
        if vrf:
            master.extend(vrf)

        fields = self.schema.get_display_fields(columns)
        self._add_active_to_fields(kwargs.get('view', self.iobj.view), fields,
                                   addnl_fields)

        drop_cols = []
        user_query_cols = self._get_user_query_cols(user_query)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        if not ifname and iftype and iftype != ["all"]:
            df = super().get(type=iftype, master=master, columns=fields,
                             addnl_fields=addnl_fields, **kwargs)
        elif not ifname and iftype != ['all']:
            df = super().get(master=master, type=['!internal'], columns=fields,
                             addnl_fields=addnl_fields, **kwargs)
        else:
            df = super().get(master=master, columns=fields,
                             addnl_fields=addnl_fields, **kwargs)

        if df.empty:
            return df

        if vlan or portmode or any(x in fields
                                   for x in ['vlan', 'vlanList', 'portmode']):
            for x in ['ipAddressList', 'ip6AddressList']:
                if x in columns or '*' in columns:
                    continue
                drop_cols.append(x)
            df = self._add_portmode(df, **kwargs)

        if vlan or "vlanList" in fields:
            df = self._add_vlanlist(df, **kwargs)

        if state or portmode:
            query_str = build_query_str([], self.schema, state=state,
                                        portmode=portmode)

            df = df.query(query_str).reset_index(drop=True)

        if vlan:
            df = self._check_vlan_match(vlan, df).reset_index(drop=True)

        if user_query:
            df = self._handle_user_query_str(df, user_query)

        if not (iftype or ifname) and 'type' in df.columns:
            return df.query('type != "internal"') \
                     .reset_index(drop=True)[fields]
        else:
            return df.reset_index(drop=True)[fields]

    def _check_vlan_match(self, vlan_filters: List[str],
                          df: pd.DataFrame) -> pd.DataFrame:
        '''Return a dataframe with rows in VLANs requested

        VLAN is treated specially because its the only field that is a list
        of integers, and can be filtered on multiple fields: vlan and vlanList
        A user filter on VLAN is a list that can contain numeric comparisons
        as well as simple integers.

        Its not made into a generic filter match because this match on VLAN
        applies only to interface table.
        '''

        opdict = {'<': operator.lt, '>': operator.gt,
                  '<=': operator.le, '>=': operator.ge,
                  '!': operator.ne, '==': operator.eq}

        def _check_cond(vlist: pd.Series, op: Callable, *args):
            fn = opdict[op]
            return vlist.apply(lambda ls: any(fn(vlan, *args) for vlan in ls))

        def _interval(ival, start_val, start_op, end_val, end_op):
            start_op = opdict[start_op]
            end_op = opdict[end_op]
            return start_op(ival, start_val) and end_op(ival, end_val)

        def extract_op(expression: Union[str, int]) -> Tuple[str, int]:
            op = '=='
            val = expression
            if isinstance(expression, str):
                if expression.startswith(('<=', '>=')):
                    val = expression[2:]
                    op = expression[:2]
                elif expression.startswith(('<', '>')):
                    val = expression[1:]
                    op = expression[:1]
                elif expression.startswith('!'):
                    val = expression[1:]
                    op = expression[:1]
            return op, val

        if not vlan_filters:
            return df

        opdict.update({'><': _interval})
        not_filters = []
        match_filters = []

        i = 0
        while i < len(vlan_filters):
            op, fval = extract_op(vlan_filters[i])
            if op.startswith('!'):
                not_filters.append(
                    f'(vlan != {fval} '
                    f'and ~@_check_cond(vlanList, "==", {fval}))')
            elif (op.startswith('>')
                  and i+1 < len(vlan_filters)
                  and isinstance(vlan_filters[i+1], str)
                  and vlan_filters[i+1].startswith('<')):
                # In this case we are checking if the user asked for an
                # an interval. So if we find a sequence of > and <,
                # we will combine the rules
                next_op, next_val = extract_op(vlan_filters[i+1])
                start_rule = f'vlan {op} {fval}'
                end_rule = f'vlan {next_op} {next_val}'
                listcheck = (f'@_check_cond(vlanList, "><", {fval}, "{op}", '
                             f'{next_val}, "{next_op}")')
                match_filters.append(
                    f'(({start_rule} and {end_rule}) or {listcheck})')
                # Increment one more time, in order to skip the
                # rule we already considered
                i += 1
            else:
                match_filters.append(
                    f'(vlan {op} {fval} '
                    f'or @_check_cond(vlanList, "{op}", {fval}))')
            i += 1

        not_str = ' and '.join(not_filters)
        match_str = ' or '.join(match_filters)
        filters = None
        if not_str and match_str:
            filters = f'({match_str}) and ({not_str})'
        elif not_str:
            filters = not_str
        elif match_str:
            filters = match_str

        if filters:
            filters += ' and (vlanList.str.len() > 0 or vlan != 0)'
            df = df.query(filters)
        return df

    def aver(self, what="", **kwargs) -> pd.DataFrame:
        """Assert that interfaces are in good state"""

        ignore_missing_peer = kwargs.pop('ignore_missing_peer', False)

        if what == "mtu-value":
            result_df = self._assert_mtu_value(**kwargs)
        else:
            result_df = self._assert_interfaces(ignore_missing_peer, **kwargs)
        return result_df

    def summarize(self, **kwargs) -> pd.DataFrame:
        """Summarize interface information"""
        self._init_summarize(**kwargs)
        if self.summary_df.empty:
            return self.summary_df

        # Loopback interfaces on Linux have "unknown" as state
        self.summary_df["state"] = self.summary_df['state'] \
                                       .map({"unknown": "up",
                                             "up": "up", "down": "down",
                                             "notConnected": "notConnected"})

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('interfaceCnt', 'ifname', 'count'),
        ]

        self._summarize_on_add_with_query = [
            ('devicesWithL2Cnt', 'master == "bridge"', 'hostname', 'nunique'),
            ('devicesWithVxlanCnt', 'type == "vxlan"', 'hostname'),
            ('ifDownCnt', 'state != "up" and adminState == "up"', 'ifname'),
            ('ifAdminDownCnt', 'adminState != "up"', 'ifname'),
            ('ifWithMultipleIPCnt', 'ipAddressList.str.len() > 1', 'ifname'),
        ]

        self._summarize_on_add_list_or_count = [
            ('uniqueMTUCnt', 'mtu'),
            ('uniqueIfTypesCnt', 'type'),
            ('speedCnt', 'speed'),
        ]

        self._summarize_on_add_stat = [
            ('ifChangesStat', 'type != "bond"', 'numChanges'),
        ]

        self._summarize_on_perdevice_stat = [
            ('ifPerDeviceStat', '', 'ifname', 'count')
        ]

        self._gen_summarize_data()

        # The rest of the summary generation is too specific to interfaces
        original_summary_df = self.summary_df
        self.summary_df = original_summary_df.explode(
            'ipAddressList').dropna(how='any')

        if not self.summary_df.empty:
            self.nsgrp = self.summary_df.groupby(by=["namespace"])
            self._add_field_to_summary(
                'ipAddressList', 'nunique', 'uniqueIPv4AddrCnt')
        else:
            self._add_constant_to_summary('uniqueIPv4AddrCnt', 0)
        self.summary_row_order.append('uniqueIPv4AddrCnt')

        self.summary_df = original_summary_df \
            .explode('ip6AddressList') \
            .dropna(how='any') \
            .query('~ip6AddressList.str.startswith("fe80:")')

        if not self.summary_df.empty:
            self.nsgrp = self.summary_df.groupby(by=["namespace"])
            self._add_field_to_summary(
                'ip6AddressList', 'nunique', 'uniqueIPv6AddrCnt')
        else:
            self._add_constant_to_summary('uniqueIPv6AddrCnt', 0)
        self.summary_row_order.append('uniqueIPv6AddrCnt')

        self._post_summarize(check_empty_col='interfaceCnt')
        return self.ns_df.convert_dtypes()

    def _assert_mtu_value(self, **kwargs) -> pd.DataFrame:
        """Workhorse routine to match MTU value"""

        columns = ["namespace", "hostname", "ifname", "state", "mtu",
                   "timestamp"]

        matchval = kwargs.pop('matchval', [])
        result = kwargs.pop('result', '')

        matchval = [int(x) for x in matchval]

        result_df = self.get(columns=columns, **kwargs) \
                        .query('ifname != "lo"')

        if result_df.empty:
            return result_df

        if not result_df.empty:
            result_df['result'] = result_df.apply(
                lambda x, matchval: 'pass' if x['mtu'] in matchval else 'fail',
                axis=1, args=(matchval,))

        if result == "fail":
            result_df = result_df.query('result == "fail"')
        elif result == "pass":
            result_df = result_df.query('result == "pass"')

        return result_df

    # pylint: disable=too-many-statements
    def _assert_interfaces(self, ignore_missing_peer: bool, **kwargs) \
            -> pd.DataFrame:
        """Workhorse routine that validates MTU match for specified input"""
        columns = kwargs.pop('columns', [])
        result = kwargs.pop('result', 'all')
        state = kwargs.pop('state', '')
        iftype = kwargs.pop('type', [])
        ifname = kwargs.pop('ifname', [])
        hostname = kwargs.pop('hostname', [])

        def _check_field(x, fld1, fld2, reason):
            if x.skipIfCheck or x.indexPeer < 0:
                return []

            if x[fld1] == x[fld2]:
                return []
            return reason

        def _check_ipaddr(x, fld1, fld2, reason):
            # If we have no peer, don't check
            if x.skipIfCheck or x.indexPeer < 0:
                return []

            if len(x[fld1]) != len(x[fld2]):
                return reason

            if (len(x[fld1]) != 0):
                if (x[fld1][0].split('/')[1] == "32" or
                    (ip_network(x[fld1][0], strict=False) ==
                        ip_network(x[fld2][0], strict=False))):
                    return []
            else:
                return []

            return reason

        columns = ['*']

        if not state:
            state = 'up'

        if not iftype:
            iftype = ['ethernet', 'bond_slave', 'subinterface', 'vlan', 'bond']

        if_df = self.get(columns=columns, type=iftype, state=state, **kwargs)
        if if_df.empty:
            if_df = pd.DataFrame(columns=self._assert_result_cols)
            if result != 'pass':
                if_df['result'] = 'fail'
                if_df['assertReason'] = 'No data'

            return if_df

        if_df = if_df.drop(columns=['description', 'routeDistinguisher',
                                    'interfaceMac'], errors='ignore')

        # filter out loopback subinterfaces
        if 'loopback' not in iftype:
            lo_pattern = r'^(lo.*)|(.*oopback.*)$'
            if_df = if_df[if_df.apply(
                lambda x: re.match(lo_pattern, x.ifname) is None,
                axis=1)]

        if_df = self._drop_junos_pifnames(if_df).reset_index()

        if if_df.empty:
            if result != 'pass':
                if_df['result'] = 'fail'
                if_df['assertReason'] = 'No data'

            return if_df

        lldpobj = self._get_table_sqobj('lldp')
        mlagobj = self._get_table_sqobj('mlag')

        # can't pass all kwargs, because lldp acceptable arguements are
        # different than interface
        namespace = kwargs.get('namespace', [])
        lldp_df = lldpobj.get(namespace=namespace, hostname=hostname) \
                         .query('peerIfname != "-"')

        mlag_df = mlagobj.get(namespace=namespace, hostname=hostname)
        if not mlag_df.empty:
            mlag_peerlinks = set(mlag_df
                                 .groupby(by=['namespace', 'hostname',
                                              'peerLink'])
                                 .groups.keys())
        else:
            mlag_peerlinks = set()

        if 'vlanList' not in if_df.columns:
            if_df['vlanList'] = [[] for i in range(len(if_df))]

        if lldp_df.empty:
            if result != 'pass':
                if_df['assertReason'] = 'No LLDP peering info'
                if_df['result'] = 'fail'

            return if_df

        # Now create a single DF where you get the MTU for the lldp
        # combo of (namespace, hostname, ifname) and the MTU for
        # the combo of (namespace, peerHostname, peerIfname) and then
        # pare down the result to the rows where the two MTUs don't match
        idf = (
            pd.merge(
                if_df,
                lldp_df,
                left_on=["namespace", "hostname", "pifname"],
                right_on=['namespace', 'hostname', 'ifname'],
                how="outer",
            )
            .drop(columns=['ifname_y', 'timestamp_y'])
            .rename({'ifname_x': 'ifname', 'timestamp_x': 'timestamp',
                     'adminState_x': 'adminState',
                     'ipAddressList_x': 'ipAddressList',
                     'ip6AddressList_x': 'ip6AddressList',
                     'portmode_x': 'portmode'}, axis=1)
        )
        idf_nonsubif = idf.query('~type.isin(["subinterface", "vlan"])')
        idf_subif = idf.query('type.isin(["subinterface", "vlan"])')

        # Replace the bond_slave port interface with the bond interface

        idf_nonsubif = idf_nonsubif.merge(
            idf_nonsubif,
            left_on=["namespace", "peerHostname", "peerIfname"],
            right_on=['namespace', 'hostname', 'ifname'],
            how="outer", suffixes=["", "Peer"])

        idf_subif = idf_subif.merge(
            idf_subif,
            left_on=["namespace", "peerHostname", "peerIfname", 'vlan'],
            right_on=['namespace', 'hostname', 'pifname', 'vlan'],
            how="outer", suffixes=["", "Peer"])

        combined_df = pd.concat(
            [idf_subif, idf_nonsubif]).reset_index(drop=True)

        combined_df = combined_df \
            .drop(columns=["hostnamePeer", "pifnamePeer",
                           "mgmtIP", "description"]) \
            .dropna(subset=['hostname', 'ifname']) \
            .drop_duplicates(subset=['namespace', 'hostname', 'ifname'])

        if not combined_df.empty and hostname:
            combined_df = self._filter_hostname(combined_df, hostname)

        if not combined_df.empty and ifname:
            combined_df = combined_df.query(f'ifname.isin({ifname})')

        if combined_df.empty:
            if result != 'pass':
                if_df['assertReason'] = 'No LLDP peering info'
                if_df['result'] = 'fail'

            return if_df

        combined_df = combined_df.fillna(
            {'mtuPeer': 0, 'speedPeer': 0, 'typePeer': '',
             'peerHostname': '', 'peerIfname': '', 'indexPeer': -1})
        for fld in ['ipAddressListPeer', 'ip6AddressListPeer', 'vlanListPeer']:
            combined_df[fld] = combined_df[fld] \
                .apply(lambda x: x if isinstance(x, np.ndarray) else [])

        combined_df['assertReason'] = combined_df.apply(
            lambda x: []
            if (x['adminState'] == 'down' or
                (x['adminState'] == "up" and x['state'] == "up"))
            else [x.reason or "Interface Down"], axis=1)

        known_hosts = set(combined_df.groupby(by=['namespace', 'hostname'])
                          .groups.keys())
        # Mark interfaces that can be skippedfrom checking because you cannot
        # find a peer
        combined_df['skipIfCheck'] = combined_df.apply(
            lambda x:
            (x.master == 'bridge') or (x.type in ['bond_slave', 'vlan']),
            axis=1)

        combined_df['indexPeer'] = combined_df.apply(
            lambda x, kh: x.indexPeer
            if (x.namespace, x.hostname) in kh else -2,
            args=(known_hosts,), axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: ['No Peer Found']
            if x.indexPeer == -1 and not x.skipIfCheck else [],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: ['Unpolled Peer']
            if x.indexPeer == -2 and not x.skipIfCheck else [],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: _check_field(x, 'mtu', 'mtuPeer', ['MTU mismatch']),
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: _check_field(
                x, 'speed', 'speedPeer', ['Speed mismatch']),
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: []
            if (x.indexPeer < 0 or
                ((x['type'] == x['typePeer']) or
                 (x['type'] == 'vlan' and x['typePeer'] == 'subinterface') or
                    (x['type'].startswith('ether') and
                     x['typePeer'].startswith('ether'))))
            else ['type mismatch'],
            axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x: [] if (x.indexPeer < 0 or
                             (x['portmode'] == x['portmodePeer']))
            else ['portMode Mismatch'], axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x:
            _check_ipaddr(x, 'ipAddressList', 'ipAddressListPeer',
                          ['IP address mismatch']), axis=1)

        # We ignore MLAG peerlinks mainly because of NXOS erroneous output.
        # NXOS displays the VLANs associated with an interface via show vlan
        # which is then further pruned out by vPC. This pruned out list needs
        # to be extracted from the vPC output and used for the peerlink
        # instead of the output of show vlan for that interface. Since most
        # platforms perform their own MLAG consistency checks, we can skip
        # doing VLAN consistency check on the peerlink.
        # TODO: A better checker for MLAG peerlinks if needed at a later time.

        combined_df['assertReason'] += combined_df.apply(
            lambda x: [] if (((x.portmode in ['access', 'trunk']) and
                              (x.indexPeer < 0 or
                               (x['vlan'] == x['vlanPeer']))) or
                             (x.portmode in ['routed', 'unknown']))
            else ['pvid Mismatch'], axis=1)

        combined_df['assertReason'] += combined_df.apply(
            lambda x, mlag_peerlinks: []
            if ((x.indexPeer > 0 and
                ((x.namespace, x.hostname, x.master) not in mlag_peerlinks) and
                 (set(x['vlanList']) == set(x['vlanListPeer']))) or
                ((x.indexPeer < 0) or
                ((x.namespace, x.hostname, x.master) in mlag_peerlinks)))
            else ['VLAN set mismatch'], args=(mlag_peerlinks,), axis=1)

        if ignore_missing_peer:
            combined_df['result'] = combined_df.apply(
                lambda x: 'fail'
                if (len(x.assertReason) and
                    (x.assertReason[0] != 'No Peer Found'))
                else 'pass', axis=1)
        else:
            combined_df['result'] = combined_df.apply(
                lambda x: 'fail' if (len(x.assertReason)) else 'pass', axis=1)

        if result == "fail":
            combined_df = combined_df.query('result == "fail"').reset_index()
        elif result == "pass":
            combined_df = combined_df.query('result == "pass"').reset_index()

        combined_df['assertReason'] = combined_df['assertReason'].apply(
            lambda x: x if len(x) else '-'
        )

        return combined_df[self._assert_result_cols]

    def _drop_junos_pifnames(self, if_df: pd.DataFrame) -> pd.DataFrame:
        """This function drops parent interfaces of Junos subinterfaces ending
        with .0 and rename them as the parent interface

        Args:
            if_df (pd.DataFrame): interface dataframe

        Returns:
            pd.DataFrame: updated dataframe
        """
        if if_df.empty:
            return if_df

        # save the parent interface name in pifname column
        if_df['pifname'] = if_df.apply(
            lambda x: x['ifname'].split('.')[0]
            if x.type in ['subinterface', 'vlan']
            else x['ifname'], axis=1)

        # save the parent interface for .0 in a different column
        # this column will be used in the final merge
        if_df['pifname_0'] = if_df.apply(
            lambda x: x.ifname.split('.')[0] if x.ifname.endswith('.0')
            else x.ifname, axis=1
        )

        # Thanks for Junos, remove all the useless parent interfaces
        # if we have a .0 interface since thats the real deal

        # remove parent interfaces of .0 from dataframe
        parent_0_df = if_df.groupby(by=['namespace', 'hostname', 'pifname_0'])\
            .size().reset_index(name='counts')

        parent_0_df = parent_0_df[parent_0_df
                                  .apply(lambda x: x.counts > 1, axis=1)] \
            .rename(columns={'pifname_0': 'ifname'}) \
            .drop(columns=['counts'])

        res_df = pd.concat([if_df[['namespace', 'hostname', 'ifname']],
                            parent_0_df]).drop_duplicates(keep=False)

        if_df = if_df.merge(
            res_df,
            on=['namespace', 'hostname', 'ifname']
        )

        if_df['type'] = if_df.apply(lambda x: 'ethernet'
                                    if x['ifname'].endswith('.0')
                                    else x['type'], axis=1)

        # map subinterface into parent interface
        if_df['ifname'] = if_df.apply(
            lambda x: x['ifname'] if not x['ifname'].endswith('.0')
            else x['pifname'], axis=1)

        return if_df

    def _add_portmode(self, df: pd.DataFrame, **kwargs):
        """Add the switchport-mode i.e. acceess/trunk/routed'''

        :param df[pd.Dataframe]: The dataframe to add vlanList to
        :param kwargs[dict]: User specified dictionary of kwargs for host/ns
        :returns: original dataframe with portmode col added and filterd
        """

        if df.empty:
            return df

        namespace = kwargs.get('namespace', [])
        hostname = kwargs.get('hostname', [])

        conf_df = self._get_table_sqobj('devconfig') \
            .get(namespace=namespace, hostname=hostname)

        devdf = self._get_table_sqobj('device') \
            .get(namespace=namespace, hostname=hostname,
                 columns=['namespace', 'hostname', 'os'],
                 ignore_neverpoll=True)

        pm_df = pd.DataFrame({'namespace': [], 'hostname': [],
                              'ifname': [], 'portmode': []})

        pm_list = []
        for row in conf_df.itertuples():
            # Check what type of device this is
            # TBD: SONIC support
            if not devdf.empty:
                nos = devdf[(devdf.namespace == row.namespace) &
                            (devdf.hostname == row.hostname)]['os'].tolist()
                if not nos:
                    continue

                nos = nos[0]
                if any(x in nos for x in ['junos', 'panos']):
                    syntax = 'junos'
                else:
                    # The way we pull out Cumulus Linux conf is also ios-like
                    syntax = 'ios'
            else:
                # Heuristics now
                if '\ninterfaces {\n' in row.config or \
                   'paloaltonetworks' in row.config:
                    syntax = 'junos'
                else:
                    syntax = 'ios'
            try:
                conf = CiscoConfParse(row.config.split('\n'), syntax=syntax)
            except Exception:  # pylint: disable=broad-except
                continue

            pm_dict = get_access_port_interfaces(conf, nos)
            pm_list.extend([{'namespace': row.namespace,
                             'hostname': row.hostname,
                             'ifname': k,
                             'portmode': 'access',
                             'vlan': v} for k, v in pm_dict.items()])
            pm_dict = get_trunk_port_interfaces(conf, nos)
            pm_list.extend([{'namespace': row.namespace,
                             'hostname': row.hostname,
                             'ifname': k,
                             'portmode': 'trunk',
                             'vlan': v} for k, v in pm_dict.items()])

        pm_df = pd.DataFrame(pm_list)

        df['portmode'] = np.where(df.ipAddressList.str.len() == 0,
                                  'unknown',
                                  'routed')
        df['portmode'] = np.where(df.ip6AddressList.str.len() != 0,
                                  'routed', df.portmode)

        if not pm_df.empty:
            df = df.merge(pm_df, how='left', on=[
                'namespace', 'hostname', 'ifname'],
                suffixes=['', '_y']) \
                .fillna({'vlan_y': 0})
            df['portmode'] = np.where(df.portmode_y.isnull(), df.portmode,
                                      df.portmode_y)

        df.loc[df.ifname == "bridge", 'portmode'] = ''
        if 'vlan_y' in df.columns:
            df['vlan'] = np.where(df.vlan_y != 0, df.vlan_y,
                                  df.vlan)
        df['vlan'] = df.vlan.astype(int)

        df['portmode'] = np.where(df.adminState != 'up', '',
                                  df.portmode)
        # handle EOS and other VXLAN ports which treat the interface
        # as a trunk port, as opposed to the access port mode of
        # the upto Cumulus 4.2.x Vxlan ports
        vxlan_ports = df.type == "vxlan"
        df.loc[vxlan_ports, 'portmode'] = df.loc[vxlan_ports] \
            .apply(lambda x: 'trunk' if x['portmode'] == 'routed'
                   else x['portmode'], axis=1)
        return df.drop(columns=['portmode_y', 'vlan_y'],
                       errors='ignore')

    def _add_vlanlist(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame():
        """Add list of active, unpruned VLANs on trunked ports

        :param df[pd.Dataframe]: The dataframe to add vlanList to
        :param kwargs[dict]: User specified dictionary of kwargs for host/ns/if
        :returns: original dataframe with vlanList col added
        """

        if df.empty:
            return df

        vlan_df = self._get_table_sqobj('vlan') \
                      .get(namespace=kwargs.get('namespace', []))

        if vlan_df.empty:
            df['vlanList'] = [[] for _ in range(len(df))]
            return df

        # Transform the list of VLANs from VLAN-oriented to interface oriented
        vlan_if_df = vlan_df.explode('interfaces') \
                            .groupby(by=['namespace', 'hostname',
                                         'interfaces'])['vlan'].unique() \
                            .reset_index() \
                            .rename(columns={'interfaces': 'ifname',
                                             'vlan': 'vlanList'})
        vlan_if_df = vlan_if_df.dropna(subset=['namespace', 'hostname'])

        vlan_if_df['vlanList'] = vlan_if_df.vlanList.apply(sorted)

        df = df.merge(vlan_if_df, how='left',
                      on=['namespace', 'hostname', 'ifname'])

        isnull = df.vlanList.isnull()
        df.loc[isnull, 'vlanList'] = pd.Series([[]] * isnull.sum()).values

        # Now remove the vlanList from all the access and routed ports
        # We leave them on the unknown ports because we may not have gotten
        # the config data to identify the port mode
        not_trunk = df.portmode.isin(["access", "routed"])
        df.loc[not_trunk, 'vlanList'] = pd.Series(
            [[]] * not_trunk.sum()).values

        return df
