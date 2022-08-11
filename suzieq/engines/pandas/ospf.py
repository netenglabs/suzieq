from typing import List
from ipaddress import IPv4Network

import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.shared.utils import build_query_str, humanize_timestamp
from suzieq.shared.schema import SchemaForTable


class OspfObj(SqPandasEngine):
    '''Backend class to handle manipulating OSPF table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'ospf'

    # pylint: disable=too-many-statements
    def _get_combined_df(self, **kwargs):
        """OSPF has info divided across multiple tables. Get a single one"""

        columns = kwargs.pop('columns', ['default'])
        state = kwargs.pop('state', '')
        user_query = kwargs.pop('query_str', '')
        hostname = kwargs.pop('hostname', [])

        cols = self.schema.get_display_fields(columns)
        self._add_active_to_fields(kwargs.get('view', self.iobj.view), cols,
                                   None)

        user_query_cols = self._get_user_query_cols(user_query)

        ifschema = SchemaForTable('ospfIf', schema=self.all_schemas)
        nbrschema = SchemaForTable('ospfNbr', schema=self.all_schemas)

        if columns not in [['default'], ['*']]:
            ifkeys = ifschema.key_fields()
            nbrkeys = nbrschema.key_fields()
            if_flds = ifschema.fields
            nbr_flds = nbrschema.fields

            ifcols = ifkeys
            nbrcols = nbrkeys
            for fld in columns:
                if fld in if_flds and fld not in ifcols:
                    ifcols.append(fld)
                elif fld in nbr_flds and fld not in nbrcols:
                    nbrcols.append(fld)
                if 'state' not in nbrcols:
                    nbrcols.append('state')
                ifcols += [x for x in ['area', 'state', 'passive']
                           if x not in ifcols]
        else:
            ifcols = ifschema.get_display_fields(columns)
            nbrcols = nbrschema.get_display_fields(columns)

        ifcols += [x for x in user_query_cols if (x in ifschema.fields
                                                  and x not in ifcols)]
        self._add_active_to_fields(kwargs.get('view', 'latest'), ifcols,
                                   None)
        nbrcols += [x for x in user_query_cols if (x in nbrschema.fields
                                                   and x not in nbrcols)]
        self._add_active_to_fields(kwargs.get('view', 'latest'), nbrcols,
                                   None)

        if 'timestamp' not in ifcols:
            ifcols.append('timestamp')

        if 'timestamp' not in nbrcols:
            nbrcols.append('timestamp')

        state_query_dict = {
            'full': '(adjState == "full" or adjState == "passive")',
            'passive': '(adjState == "passive")',
            'other': '(adjState != "full" and adjState != "passive")',
            '!full': '(adjState != "full")',
            '!passive': '(adjState != "passive")',
            '!other': '(adjState == "full" or adjState == "passive")',
        }

        if state:
            query_str = state_query_dict.get(state, '')
            cond_prefix = ' and '
        else:
            query_str = ''
            cond_prefix = ''

        host_query_str = build_query_str([], ifschema, ignore_regex=False,
                                         hostname=hostname)
        if host_query_str:
            query_str += f'{cond_prefix}{host_query_str}'

        df = self._get_table_sqobj('ospfIf') \
                 .get(columns=ifcols, **kwargs)
        nbr_df = self._get_table_sqobj('ospfNbr') \
                     .get(columns=nbrcols, **kwargs)
        if nbr_df.empty:
            return df

        merge_cols = [x for x in ['namespace', 'hostname', 'ifname']
                      if x in nbr_df.columns]
        # Merge the two tables
        df = df.merge(nbr_df, on=merge_cols, how='left') \
               .fillna({'peerIP': '-', 'numChanges': 0,
                        'lastChangeTime': 0}) \
               .fillna('')

        # This is because some NOS have the ipAddress in nbr table and some in
        # interface table. Nbr table wins over interface table if present
        if 'ipAddress_y' in df:
            df['ipAddress'] = np.where(
                df['ipAddress_x'] == "",
                df['ipAddress_y'], df['ipAddress_x'])

        if columns == ['*']:
            df = df.drop(columns=['area_y', 'instance_y', 'vrf_y',
                                  'ipAddress_x', 'ipAddress_y', 'areaStub_y',
                                  'sqvers_x', 'timestamp_y'],
                         errors='ignore') \
                .rename(columns={
                    'instance_x': 'instance', 'areaStub_x': 'areaStub',
                    'area_x': 'area', 'vrf_x': 'vrf',
                    'state_x': 'ifState', 'state_y': 'adjState',
                    'active_x': 'active', 'timestamp_x': 'timestamp'}) \
                .fillna({'peerIP': '-', 'numChanges': 0,
                         'lastChangeTime': 0})
        else:
            df = df.rename(columns={'vrf_x': 'vrf', 'area_x': 'area',
                                    'state_x': 'ifState',
                                    'state_y': 'adjState',
                                    'timestamp_x': 'timestamp'})
            df = df.drop(list(df.filter(regex='_y$')), axis=1) \
                   .drop(columns=['ipAddress_x'], errors='ignore') \
                   .fillna({'peerIP': '-', 'numChanges': 0,
                            'lastChangeTime': 0})
        if df.empty:
            return df

        if 'state' in df.columns:
            # Need this logic if the user specfies only one of adjState
            # or ifState in the columns field. The above renaming of state_x
            # and state_y will not work in that case, and this is what we
            # have to do.
            if 'ifState' in cols:
                df = df.rename(columns={'state': 'ifState'})
            else:
                df = df.rename(columns={'state': 'adjState'})
        if 'lastChangeTime' in df.columns:
            df['lastChangeTime'] = np.where(df.lastChangeTime == '-',
                                            0, df.lastChangeTime)
        # Fill the adjState column with passive if passive
        if 'passive' in df.columns and 'adjState' in df.columns:
            df.loc[df['adjState'] == '', 'adjState'] = df['passive']
            df.loc[df['adjState'].eq(True), 'adjState'] = 'passive'
            df.loc[df['adjState'].eq(False), 'adjState'] = 'fail'
            df.loc[df['adjState'] == 'passive', 'peerIP'] = ''
            df.loc[df['adjState'] == 'passive', 'peerRouterId'] = ''

            df.drop(columns=['passive'], inplace=True)

        final_df = df
        if 'active_x' in final_df.columns:
            final_df = final_df.rename(columns={'active_x': 'active'})
        if 'peerHostname' in cols or 'peerIfname' in cols:
            final_df = self._get_peernames(final_df, cols, hostname=hostname,
                                           **kwargs)
        if query_str:
            final_df = final_df.query(query_str).reset_index(drop=True)

        if user_query and not final_df.empty:
            final_df = self._handle_user_query_str(final_df, user_query)
        # Move the timestamp column to the end

        return final_df.reset_index(drop=True)[cols]

    def get(self, **kwargs):
        return self._get_combined_df(**kwargs)

    def summarize(self, **kwargs):
        """Describe the data"""

        # Discard these
        kwargs.pop('columns', None)

        # 'ospfIf' is ignored
        self._init_summarize(**kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('peerCnt', 'hostname', 'count'),
        ]

        self._summarize_on_add_with_query = [
            ('stubbyPeerCnt', 'areaStub', 'areaStub'),
            ('passivePeerCnt', 'adjState == "passive"', 'ifname'),
            ('unnumberedPeerCnt', 'isUnnumbered', 'isUnnumbered'),
            ('failedPeerCnt', '~adjState.isin(["passive", "full"])',
             'ifname'),
        ]

        self._summarize_on_add_list_or_count = [
            ('area', 'area'),
            ('vrf', 'vrf'),
            ('helloTime', 'helloTime'),
            ('deadTime', 'deadTime'),
            ('retxTime', 'retxTime'),
            ('networkType', 'networkType'),
        ]

        self.summary_df['lastChangeTime'] = np.where(
            self.summary_df.lastChangeTime.isnull(), 0,
            self.summary_df.lastChangeTime)

        self.summary_df['lastChangeTime'] = humanize_timestamp(
            self.summary_df.lastChangeTime, self.cfg.get('analyzer', {})
            .get('timezone', None))

        self.summary_df['lastChangeTime'] = (
            self.summary_df['timestamp'] - self.summary_df['lastChangeTime'])
        self.summary_df['lastChangeTime'] = self.summary_df['lastChangeTime'] \
            .apply(lambda x: x.round('s'))

        self._summarize_on_add_stat = [
            ('adjChangesStat', '', 'numChanges'),
            ('upTimeStat', 'adjState == "full"', 'lastChangeTime'),
        ]

        self._gen_summarize_data()
        self._post_summarize()
        return self.ns_df.convert_dtypes()

    def aver(self, **kwargs):
        """Assert that the OSPF state is OK"""

        kwargs.pop('columns', [])
        columns = ['*']

        result = kwargs.pop('result', 'all')
        kwargs.pop('state', '')
        # we have to not filter hostname at this point because we need to
        #   understand neighbor relationships

        ospf_df = self.get(columns=columns, **kwargs)

        if not ospf_df.empty:
            ospf_df = ospf_df.query('ifState != "adminDown"') \
                             .reset_index(drop=True)

        if ospf_df.empty:
            return pd.DataFrame(columns=columns)

        columns.extend(['peerHostname', 'peerIfname'])
        ospf_df = self._get_peernames(ospf_df, columns)

        ospf_df["assertReason"] = [[]]*ospf_df.shape[0]
        df = (
            ospf_df[ospf_df["routerId"] != ""]
            .groupby(["routerId", "namespace"], as_index=False)[["hostname",
                                                                 "namespace"]]
            .agg(lambda x: x.unique().tolist())
        ).dropna(how='any')

        # df is a dataframe with each row containing the routerId and the
        # corresponding list of hostnames with that routerId. In a good
        # configuration, the list must have exactly one entry.
        if not df.empty:
            # This check is because we don't get routerID with Arista boxes
            ospf_df['assertReason'] = (
                ospf_df.merge(df, on=["routerId"], how="outer")
                .apply(lambda x: ["duplicate routerId {}".format(
                    x["hostname_y"])]
                    if (x["hostname_y"] is not np.nan and
                        len(x['hostname_y']) != 1) else [], axis=1))

        ok_df = ospf_df \
            .query('adjState.isin(["passive", "full"])') \
            .reset_index(drop=True)
        failed_df = ospf_df \
            .query('~adjState.isin(["passive", "full"]) and '
                   'ifState != "down"') \
            .reset_index(drop=True)
        ifdown_df = ospf_df \
            .query('~adjState.isin(["full", "passive"]) and '
                   'ifState == "down"') \
            .reset_index(drop=True)
        ifdown_df['assertReason'] += \
            ifdown_df.ifState.apply(lambda x: ['ifdown'])

        # Validate loopback interfaces are of the right network type
        if not ok_df.empty:
            ok_df['assertReason'] += ok_df.apply(
                lambda x: ['network type !loopback']
                if (any(ele in x.ifname for ele in ['lo', 'oopbac']) and
                    x.networkType != "loopback") else [], axis=1)

        if failed_df.empty:
            return self._create_aver_result([ok_df, ifdown_df], result)

        # We have the MTU mismatch which requires us to pull the MTU from the
        # interfaces table
        ifdf = self._get_table_sqobj('interfaces').get(
            namespace=kwargs.get('namespace', []),
            hostname=kwargs.get('hostname', []),
            columns=['namespace', 'hostname', 'ifname', 'mtu',
                     'ipAddressList'],
            query_str='ipAddressList.str.len() != 0')

        if not ifdf.empty:
            ifdf = ifdf.explode('ipAddressList')
            ifdf['ipAddressList'] = ifdf.ipAddressList.str.split('/').str[0]
            failed_df = failed_df.merge(
                ifdf, how='left',
                on=['namespace', 'hostname', 'ifname'],
                suffixes=('', '_y'))
            check_mtu = True
        else:
            check_mtu = False

        peer_df = failed_df.merge(
            failed_df, how='left',
            left_on=["namespace", "hostname", "ifname"],
            right_on=["namespace", "peerHostname", "peerIfname"]) \
            .rename(columns={'assertReason_x': 'assertReason'}) \
            .dropna(subset=['ipAddress_x', 'ipAddress_y']) \
            .fillna({'isUnnumbered_y': False})

        if peer_df.empty:
            # We're unable to find a peer but the sessions have failed
            failed_df['assertReason'] = failed_df.apply(
                lambda x: ['Loopback not configured passive']
                if x['networkType'] == 'loopback' else ['No Peer Found'],
                axis=1)

            return self._create_aver_result([ok_df, ifdown_df, failed_df],
                                            result)

        peer_df = peer_df.drop(columns=['assertReason_y'])

        # Now start comparing the various parameters
        # pylint: disable=condition-evals-to-constant
        peer_df["assertReason"] += peer_df.apply(
            lambda x: ["subnet mismatch"]
            if (
                (x["isUnnumbered_x"] != x["isUnnumbered_y"])
                or (
                    (('ipAddress_y == ""') or
                     ((IPv4Network(x["ipAddress_x"], strict=False)
                       != IPv4Network(x["ipAddress_y"], strict=False)))))
            )
            else [],
            axis=1,
        )

        peer_df["assertReason"] += peer_df.apply(
            lambda x: ["area mismatch"]
            if (x["area_x"] != x["area_y"]) else [], axis=1)

        peer_df["assertReason"] += peer_df.apply(
            lambda x: ["area stub mismatch"]
            if (x["areaStub_x"] != x["areaStub_y"]) else [], axis=1)

        peer_df["assertReason"] += peer_df.apply(
            lambda x: ["Hello timers mismatch"]
            if x["helloTime_x"] != x["helloTime_y"]
            else [],
            axis=1,
        )
        peer_df["assertReason"] += peer_df.apply(
            lambda x: ["Dead timer mismatch"]
            if x["deadTime_x"] != x["deadTime_y"]
            else [],
            axis=1,
        )
        peer_df["assertReason"] += peer_df.apply(
            lambda x: ["network type mismatch"]
            if x["networkType_x"] != x["networkType_y"]
            else [],
            axis=1,
        )
        peer_df["assertReason"] += peer_df.apply(
            lambda x: ["vrf mismatch"] if x["vrf_x"] != x["vrf_y"] else [],
            axis=1,
        )

        if check_mtu:
            peer_df["assertReason"] += peer_df.apply(
                lambda x: ["MTU mismatch"]
                if x["mtu_x"] != x["mtu_y"] else [],
                axis=1,
            )

        # Now walk through and label all the failed sessions for
        # which we have no reason
        peer_df['assertReason'] += peer_df.apply(
            lambda x: ["No Peer Found"]
            if (x['adjState_x'] == "fail" and
                x['assertReason'].str.len() == 0)
            else [],
            axis=1)

        result_df = (
            peer_df.rename(
                index=str,
                columns={
                    "hostname_x": "hostname",
                    "ifname_x": "ifname",
                    "vrf_x": "vrf",
                    "timestamp_x": "timestamp",
                    "adjState_x": "adjState",
                },
            )[["namespace", "hostname", "ifname", "vrf", "adjState",
               "assertReason", "timestamp"]]
        )

        return self._create_aver_result([ok_df, ifdown_df, result_df],
                                        result)

    def _get_peernames(self, df: pd.DataFrame, columns: List[str],
                       **kwargs) -> pd.DataFrame:
        """Fill in columns of peerhostname and peerifname if requested

        Using a combination of LLDP info, if available and without it,
        this routine tries to fill in the columns of peerhostname and
        peerifname for the relevant rows. In the absence of LLDP info,
        filling in peerifname is very error-prone especially in the
        presence of unnumbered interfaces.

        Args:
            df: The OSPF dataframe with the relevant dependent cols
            columns: List of column names provided by user
            kwargs: User specified list for hostname/namespace etc.

        Returns:
            The OSPF dataframe with the peerHostname and peerifname
            filled in
        """

        if df.empty or not any(x in columns
                               for x in ['peerHostname', 'peerIfname', '*',
                                         'default']):
            return df

        df['peerHostname'] = ''
        df['peerIfname'] = ''

        nfdf = df.query('adjState == "passive"').reset_index()
        newdf = df.query('adjState != "passive"').reset_index() \
            .drop('peerHostname', axis=1, errors='ignore')
        if newdf.empty:
            return df

        lldp_df = self._get_table_sqobj('lldp').get(
            namespace=kwargs.get('namespace', []),
            hostname=kwargs.get('hostname', []),
            use_bond='True')

        if lldp_df.empty:
            # Try a match entirely within ospf, but we can't
            # get ifname effectively in cases of unnumbered
            newdf['matchIP'] = newdf.ipAddress.str.split('/').str[0]
            newdf = newdf \
                .merge(newdf[['namespace', 'hostname', 'vrf',
                              'matchIP']],
                       left_on=['namespace', 'vrf', 'peerIP'],
                       right_on=['namespace', 'vrf', 'matchIP'],
                       suffixes=["", "_y"]) \
                .rename(columns={'hostname_y': 'peerHostname'}) \
                .drop_duplicates(subset=['namespace', 'hostname',
                                         'vrf', 'ifname']) \
                .drop(columns=['matchIP', 'matchIP_y', 'timestamp_y'],
                      errors='ignore')
            if 'peerIfname' in columns:
                newdf['peerIfname'] = ''
        else:
            # In case of Junos, the OSPF interface name is a subif of
            # the interface name. So, create a new column with the
            # orignal interface name.
            newdf['lldpIfname'] = newdf['ifname'].str.split('.').str[0]

            newdf = newdf.merge(
                lldp_df[['namespace', 'hostname', 'ifname',
                         'peerHostname', 'peerIfname']],
                left_on=['namespace', 'hostname', 'lldpIfname'],
                right_on=['namespace', 'hostname', 'ifname'],
                how='outer', suffixes=('', '_y')) \
                .drop(columns=['ifname_y', 'lldpIfname', 'peerIfname']) \
                .rename(columns={'peerIfname_y': 'peerIfname'}) \
                .dropna(subset=['hostname', 'vrf', 'ifname'], how='any')\
                .fillna('')

        if newdf.empty:
            newdf = df.query('adjState != "passive"').reset_index(drop=True)
            newdf['peerHostname'] = ''

        # Lets find the rows without peerHostnames
        nopeer_df = newdf.query('peerHostname == ""')
        if not nopeer_df.empty:
            peerdf = newdf.query('peerHostname != ""')
            nopeer_df = nopeer_df.drop(columns=['peerHostname', 'peerIfname'],
                                       errors='ignore')
            # We need to look deeper to see if we can figure out the peers
            addr_df = self._get_table_sqobj('address').get(
                namespace=kwargs.get('namespace', []),
                hostname=kwargs.get('hostname', []),
                type='!loopback',
                columns=['namespace', 'hostname', 'vrf', 'ifname', 'state',
                         'ipAddressList'],
                query_str='ipAddressList.str.len() != 0')
            if not addr_df.empty:
                addr_df = addr_df.explode('ipAddressList')
                addr_df['ipAddressList'] = addr_df.ipAddressList \
                                                  .str.split('/').str[0]
                nopeer_df = nopeer_df.merge(
                    addr_df,
                    left_on=['namespace', 'peerIP'],
                    right_on=['namespace', 'ipAddressList'],
                    suffixes=['', '_y'], how='left') \
                    .rename(columns={'hostname_y': 'peerHostname',
                                     'ifname_y': 'peerIfname'}) \
                    .drop(columns=['state', 'ipAddressList'],
                          errors='ignore') \
                    .fillna('')

        if not nopeer_df.empty:
            final_df = pd.concat([nfdf, peerdf, nopeer_df])
        else:
            final_df = pd.concat([nfdf, newdf])

        return final_df

    def _create_aver_result(self, dflist: List[pd.DataFrame],
                            result: str) -> pd.DataFrame:
        """Create a result dataframe from list and return a single df

        A common function to concat all the different dataframes
        created during assert such as passed_df, failed_df etc.,
        create a single dataframe and return the list given user input
        to return all rows or just some

        Args:
            dflist: List[pd.DataFrame]
            result: str: user specification of what result to return

        Returns:
            The assert result dataframe
        """
        ospf_df = pd.concat(dflist)
        ospf_df['result'] = ospf_df.assertReason.apply(
            lambda x: 'fail' if x else 'pass')
        # Weed out the loopback, SVI interfaces as they have no LLDP peers
        if result and result != "all":
            ospf_df = ospf_df.query(f'result == "{result}"')

        return ospf_df[['namespace', 'hostname', 'vrf', 'ifname', 'adjState',
                        'assertReason', 'result']] \
            .reset_index(drop=True)
