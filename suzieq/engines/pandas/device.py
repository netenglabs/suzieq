import operator
from packaging import version

import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine
from suzieq.shared.utils import humanize_timestamp


class DeviceObj(SqPandasEngine):
    '''Backend class to handle manipulating Device table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'device'

    # pylint: disable=too-many-statements
    def get(self, **kwargs):
        """Get the information requested"""
        view = kwargs.get('view', self.iobj.view)
        columns = kwargs.pop('columns', ['default'])
        user_query = kwargs.pop('query_str', '')
        status = kwargs.pop('status', '')
        os_version = kwargs.pop('version', '')
        os = kwargs.get('os', '')
        ignore_neverpoll = kwargs.pop('ignore_neverpoll', False)

        addnl_fields = []
        fields = self.schema.get_display_fields(columns)
        self._add_active_to_fields(view, fields, addnl_fields)

        # os is not included in the default column list. Why? I was dumb
        if os and 'os' not in fields:
            addnl_fields.append('os')

        for col in ['namespace', 'hostname', 'status', 'address']:
            if col not in fields:
                addnl_fields.append(col)

        if 'uptime' in fields and 'bootupTimestamp' not in fields:
            addnl_fields.append('bootupTimestamp')

        user_query_cols = self._get_user_query_cols(user_query)
        addnl_fields += [x for x in user_query_cols if x not in addnl_fields]

        getcols = list(set(fields + ['timestamp']))

        df = super().get(active_only=False, addnl_fields=addnl_fields,
                         columns=getcols, **kwargs)
        if view == 'latest' and 'status' in df.columns:
            df['status'] = np.where(df.active, df['status'], 'dead')

        poller_df = pd.DataFrame()
        if not ignore_neverpoll:
            poller_df = self._get_table_sqobj('sqPoller').get(
                namespace=kwargs.get('namespace', []),
                hostname=kwargs.get('hostname', []),
                service='device',
                columns='namespace hostname status timestamp'.split())

        if not poller_df.empty:
            # Identify the address to namespace/hostname mapping
            addr_dict = {f"{x['namespace']}-{x['address']}": x['hostname']
                         for x in df[['namespace', 'address', 'hostname']]
                         .to_dict(orient='records')}

            poller_df['hostname'] = poller_df.apply(
                lambda x, y: y.get(f"{x['namespace']}-{x['hostname']}",
                                   x['hostname']),
                args=(addr_dict,), axis=1)

            poller_df = poller_df\
                .drop_duplicates(subset=['namespace', 'hostname'],
                                 keep='last') \
                .reset_index(drop=True)

            df = df.merge(poller_df, on=['namespace', 'hostname'],
                          how='outer', suffixes=['', '_y'])  \
                .fillna({'bootupTimestamp': 0,
                         'active': True})

            df.timestamp = np.where(df['timestamp'].isna(),
                                    df['timestamp_y'], df['timestamp'])

            # For some reason the fillna operation removes the timezone, so we
            # use where to detect NaN values and to replace them
            df = df.fillna('N/A')

            df.status = np.where(
                (df['status_y'] != 0) & (df['status_y'] != 200) &
                (df['status'] == "N/A"),
                'neverpoll', df['status'])

            if 'version' in df.columns:
                df['version'] = np.where(df.status_y == 418, 'unsupported',
                                         df.version)
            if 'os' in df.columns:
                df['os'] = np.where(df.status_y == 418, 'unsupported',
                                    df.os)
            if 'model' in df.columns:
                df['model'] = np.where(df.status_y == 418, 'unsupported',
                                       df.model)
            df = df[df.status != 'N/A']
            if 'address' in df.columns:
                df.address = np.where(df['address'] == 'N/A', df['hostname'],
                                      df['address'])

        if 'uptime' in columns or columns == ['*']:
            uptime_cols = (df['timestamp'] -
                           humanize_timestamp(df['bootupTimestamp']*1000,
                           self.cfg.get('analyzer', {}).get('timezone',
                                                            None)))
            uptime_cols = pd.to_timedelta(uptime_cols, unit='s')
            df.insert(len(df.columns)-1, 'uptime', uptime_cols)

        if df.empty:
            return df

        # The poller merge kills the filtering we did earlier, so redo:
        if status:
            df = df.loc[df.status.isin(status)]
        if os_version:
            opdict = {'>': operator.gt, '<': operator.lt, '>=': operator.ge,
                      '<=': operator.le, '=': operator.eq, '!': operator.ne}
            op = operator.eq
            for osv in os_version:
                # Introduced in 0.19.1, we do this for backwards compatibility
                osv = osv.replace('!=', '!')
                for elem, val in opdict.items():
                    if osv.startswith(elem):
                        osv = osv.replace(elem, '')
                        op = val
                        break

                df = df.loc[df.version.apply(
                    lambda x: op(version.LegacyVersion(x),
                                 version.LegacyVersion(osv)))]

        df = self._handle_user_query_str(df, user_query)

        # if poller has failed completely, Can mess up the order of columns
        return df.reset_index(drop=True)[fields]

    def summarize(self, **kwargs):
        """Summarize device information across namespace"""

        self._init_summarize(**kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
        ]

        self._summarize_on_add_with_query = [
            ('downDeviceCnt', 'status == "dead"', 'hostname', 'nunique'),
            ('unpolledDeviceCnt', 'status == "neverpoll"', 'hostname',
             'nunique'),
        ]

        self._summarize_on_add_list_or_count = [
            ('vendorCnt', 'vendor'),
            ('modelCnt', 'model'),
            ('archCnt', 'architecture'),
            ('versionCnt', 'version'),
        ]

        self._summarize_on_add_stat = [
            ('upTimeStat', 'status != "neverpoll"', 'uptime')
        ]

        self._gen_summarize_data()
        self._post_summarize(check_empty_col='deviceCnt')
        return self.ns_df.convert_dtypes()
