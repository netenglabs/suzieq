from ipaddress import IPv4Network
import pandas as pd
import numpy as np

from .engineobj import SqPandasEngine
from suzieq.utils import SchemaForTable, build_query_str, humanize_timestamp


class OspfObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'ospf'

    def _get_combined_df(self, **kwargs):
        """OSPF has info divided across multiple tables. Get a single one"""

        columns = kwargs.pop('columns', ['default'])
        state = kwargs.pop('state', '')
        addnl_fields = kwargs.pop('addnl_fields', self.iobj._addnl_fields)
        addnl_nbr_fields = self.iobj._addnl_nbr_fields
        user_query = kwargs.pop('query_str', '')
        hostname = kwargs.pop('hostname', [])

        cols = self.schema.get_display_fields(columns)

        if columns == ['*']:
            cols.remove('sqvers')

        ifschema = SchemaForTable('ospfIf', schema=self.all_schemas)
        nbrschema = SchemaForTable('ospfNbr', schema=self.all_schemas)

        if (columns != ['default']) and (columns != ['*']):
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
        else:
            ifcols = ifschema.get_display_fields(columns)
            nbrcols = nbrschema.get_display_fields(columns)

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

        df = self.get_valid_df('ospfIf', addnl_fields=addnl_fields,
                               columns=ifcols, **kwargs)
        nbr_df = self.get_valid_df('ospfNbr', addnl_fields=addnl_nbr_fields,
                                   columns=nbrcols, **kwargs)
        if nbr_df.empty:
            return df

        merge_cols = [x for x in ['namespace', 'hostname', 'ifname']
                      if x in nbr_df.columns]
        # Merge the two tables
        df = df.merge(nbr_df, on=merge_cols, how='left')

        # This is because some NOS have the ipAddress in nbr table and some in
        # interface table. Nbr table wins over interface table if present
        if 'ipAddress_y' in df:
            df['ipAddress'] = np.where(
                df['ipAddress_y'] == "",
                df['ipAddress_x'], df['ipAddress_y'])
            df['ipAddress'] = np.where(df['ipAddress'], df['ipAddress'],
                                       df['ipAddress_x'])

        if columns == ['*']:
            df = df.drop(columns=['area_y', 'instance_y', 'vrf_y',
                                  'ipAddress_x', 'ipAddress_y', 'areaStub_y',
                                  'sqvers_x', 'timestamp_y'],
                         errors='ignore') \
                .rename(columns={
                    'instance_x': 'instance', 'areaStub_x': 'areaStub',
                    'area_x': 'area', 'vrf_x': 'vrf',
                    'state_x': 'ifState', 'state_y': 'adjState',
                    'active_x': 'active', 'timestamp_x': 'timestamp'})
        else:
            df = df.rename(columns={'vrf_x': 'vrf', 'area_x': 'area',
                                    'state_x': 'ifState',
                                    'state_y': 'adjState',
                                    'timestamp_x': 'timestamp'})
            df = df.drop(list(df.filter(regex='_y$')), axis=1) \
                   .drop(['ipAddress_x'], axis=1, errors='ignore') \
                   .fillna({'peerIP': '-', 'numChanges': 0,
                            'lastChangeTime': 0})

        if df.empty:
            return df

        if 'lastChangeTime' in df.columns:
            df['lastChangeTime'] = np.where(df.lastChangeTime == '-',
                                            0, df.lastChangeTime)
        # Fill the adjState column with passive if passive
        if 'passive' in df.columns:
            df.loc[df['adjState'].isnull(), 'adjState'] = df['passive']
            df.loc[df['adjState'].eq(True), 'adjState'] = 'passive'
            df.loc[df['adjState'].eq(False), 'adjState'] = 'fail'
            df.loc[df['adjState'] == 'passive', 'peerIP'] = ''
            df.loc[df['adjState'] == 'passive', 'peerRouterId'] = ''

            df.drop(columns=['passive'], inplace=True)

        df.bfill(axis=0, inplace=True)

        if 'peerHostname' in columns or (columns in [['*'], ['default']]):
            nfdf = df.query('adjState != "full"').reset_index()
            nfdf['peerHostname'] = ''
            newdf = df.query('adjState == "full"').reset_index() \
                .drop('peerHostname', axis=1, errors='ignore')
            if not newdf.empty:
                newdf['matchIP'] = newdf.ipAddress.str.split('/').str[0]
                newdf = newdf.merge(newdf[['namespace', 'hostname', 'vrf',
                                           'matchIP']],
                                    left_on=['namespace', 'vrf', 'peerIP'],
                                    right_on=['namespace', 'vrf', 'matchIP'],
                                    suffixes=["", "_y"]) \
                    .rename(columns={'hostname_y': 'peerHostname'}) \
                    .drop_duplicates(subset=['namespace', 'hostname',
                                             'vrf', 'ifname']) \
                    .drop(columns=['matchIP', 'matchIP_y', 'timestamp_y'],
                          errors='ignore')

                if newdf.empty:
                    newdf = df.query('adjState == "full"').reset_index()
                    newdf['peerHostname'] = ''
                final_df = pd.concat([nfdf, newdf])
            else:
                final_df = df
        else:
            final_df = df.drop(list(df.filter(regex='_y$')), axis=1) \
                         .rename({'timestamp_x': 'timestamp'})

        if query_str:
            final_df = final_df.query(query_str).reset_index(drop=True)

        if user_query and not final_df.empty:
            final_df = self._handle_user_query_str(final_df, user_query)
        # Move the timestamp column to the end
        return final_df[cols]

    def get(self, **kwargs):
        return self._get_combined_df(**kwargs)

    def summarize(self, **kwargs):
        """Describe the data"""

        # Discard these
        kwargs.pop('columns', None)

        # 'ospfIf' is ignored
        self._init_summarize('ospfIf', **kwargs)
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
            ('failedPeerCnt', 'adjState != "passive" and nbrCount == 0',
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
        columns = [
            "namespace",
            "hostname",
            "vrf",
            "ifname",
            "state",
            "routerId",
            "helloTime",
            "deadTime",
            "passive",
            "ipAddress",
            "isUnnumbered",
            "areaStub",
            "networkType",
            "timestamp",
            "area",
            "nbrCount",
        ]

        status = kwargs.pop('status', 'all')
        # we have to not filter hostname at this point because we need to
        #   understand neighbor relationships

        ospf_df = self.get_valid_df("ospfIf", columns=columns,
                                    state="!adminDown", **kwargs)
        if ospf_df.empty:
            return pd.DataFrame(columns=columns)

        ospf_df["assertReason"] = [[] for _ in range(len(ospf_df))]
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

        # Now  peering match
        lldp_df = self._get_table_sqobj('lldp').get(
            namespace=kwargs.get('namespace', []), columns=['default'])
        if lldp_df.empty:
            ospf_df = ospf_df[~(ospf_df.ifname.str.contains('loopback') |
                                ospf_df.ifname.str.contains('Vlan'))]
            ospf_df['assertReason'] = 'No LLDP peering info'
            ospf_df['assert'] = 'fail'
            return ospf_df[['namespace', 'hostname', 'vrf', 'ifname',
                            'assertReason', 'assert']]

        # Create a single massive DF with fields populated appropriately
        use_cols = [
            "namespace",
            "routerId",
            "hostname",
            "vrf",
            "ifname",
            "helloTime",
            "deadTime",
            "passive",
            "ipAddress",
            "areaStub",
            "isUnnumbered",
            "networkType",
            "area",
            "timestamp",
            "lldpIfname"
        ]

        # In case of Junos, the OSPF interface name is a subif of
        # the interface name. So, create a new column with the
        # orignal interface name.
        ospf_df['lldpIfname'] = ospf_df['ifname'].str.split('.').str[0]
        int_df = ospf_df[use_cols].merge(
            lldp_df,
            left_on=["namespace", "hostname", "lldpIfname"],
            right_on=['namespace', 'hostname', "ifname"],
            suffixes=("", "_y")) \
            .dropna(how="any")

        if int_df.empty:
            # Weed out the loopback, SVI interfaces as they have no LLDP peers
            if status == "pass":
                ospf_df = ospf_df[(ospf_df.ifname.str.contains('loopback') |
                                   ospf_df.ifname.str.contains('Vlan'))]
                ospf_df['assertReason'] = []
                ospf_df['assert'] = 'pass'
            else:
                ospf_df = ospf_df[~(ospf_df.ifname.str.contains('loopback') |
                                    ospf_df.ifname.str.contains('Vlan'))]
                ospf_df['assertReason'] = 'No LLDP peering info'
                ospf_df['assert'] = 'fail'

            return ospf_df[['namespace', 'hostname', 'vrf', 'ifname',
                            'assertReason', 'assert']]

        peer_df = ospf_df.merge(
            int_df,
            left_on=["namespace", "hostname", "lldpIfname"],
            right_on=["namespace", "peerHostname", "peerIfname"]) \
            .dropna(how="any")

        if peer_df.empty:
            ospf_df = ospf_df[~(ospf_df.ifname.str.contains('loopback') |
                                ospf_df.ifname.str.contains('Vlan'))]
            ospf_df['assertReason'] = 'No LLDP peering info'
            ospf_df['assert'] = 'fail'
        else:
            ospf_df = peer_df
            # Now start comparing the various parameters
            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["subnet mismatch"]
                if (
                    (x["isUnnumbered_x"] != x["isUnnumbered_y"])
                    and (
                        IPv4Network(x["ipAddress_x"], strict=False)
                        != IPv4Network(x["ipAddress_y"], strict=False)
                    )
                )
                else [],
                axis=1,
            )
            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["area mismatch"]
                if (x["area_x"] != x["area_y"]) else [], axis=1)

            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["area stub mismatch"]
                if (x["areaStub_x"] != x["areaStub_y"]) else [], axis=1)

            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["Hello timers mismatch"]
                if x["helloTime_x"] != x["helloTime_y"]
                else [],
                axis=1,
            )
            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["Dead timer mismatch"]
                if x["deadTime_x"] != x["deadTime_y"]
                else [],
                axis=1,
            )
            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["network type mismatch"]
                if x["networkType_x"] != x["networkType_y"]
                else [],
                axis=1,
            )
            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["passive config mismatch"]
                if x["passive_x"] != x["passive_y"]
                else [],
                axis=1,
            )
            ospf_df["assertReason"] += ospf_df.apply(
                lambda x: ["vrf mismatch"] if x["vrf_x"] != x["vrf_y"] else [],
                axis=1,
            )

        # Fill up a single assert column now indicating pass/fail
        ospf_df['assert'] = ospf_df.apply(lambda x: 'pass'
                                          if not len(x['assertReason'])
                                          else 'fail', axis=1)

        result = (
            ospf_df.rename(
                index=str,
                columns={
                    "hostname_x": "hostname",
                    "ifname_x": "ifname",
                    "vrf_x": "vrf",
                    "timestamp_x": "timestamp",
                },
            )[["namespace", "hostname", "ifname", "vrf", "assert",
               "assertReason", "timestamp"]].explode(column='assertReason')
            .fillna({'assertReason': '-'})
        )

        if status == "pass":
            return result.query('assertReason == "-"')
        elif status == "fail":
            return result.query('assertReason != "-"')

        return result.reset_index(drop=True)
