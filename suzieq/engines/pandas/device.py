import numpy as np
from .engineobj import SqPandasEngine
from suzieq.sqobjects.sqPoller import SqPollerObj


class DeviceObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'device'

    def get(self, **kwargs):
        """Get the information requested"""
        view = kwargs.get('view', self.iobj.view)
        columns = kwargs.get('columns', ['default'])
        addnl_fields = kwargs.pop('addnl_fields', [])
        user_query = kwargs.pop('query_str', '')

        drop_cols = []

        if 'active' not in addnl_fields+columns and columns != ['*']:
            addnl_fields.append('active')
            drop_cols.append('active')

        if (not ((columns == ['default']) or (columns == ['*'])) and
                'address' not in columns):
            addnl_fields.append('address')
            drop_cols.append('address')

        df = super().get(active_only=False, addnl_fields=addnl_fields,
                         **kwargs)
        if view == 'latest' and 'status' in df.columns:
            df['status'] = np.where(df.active, df['status'], 'dead')

        poller_df = SqPollerObj(context=self.ctxt).get(
            namespace=kwargs.get('namespace', []),
            hostname=kwargs.get('hostname', []),
            service='device',
            columns='namespace hostname status'.split())

        if not poller_df.empty:
            df = df.merge(poller_df, left_on=['namespace', 'hostname'],
                          right_on=['namespace', 'hostname'],
                          how='outer', suffixes=['', '_y'])  \
                .fillna({'bootupTimestamp': 0, 'timestamp': 0,
                         'active': True}) \
                .fillna('N/A')

            df.status = np.where(df['status_y'] != 0, 'pollfail',
                                 df['status'])
            df.timestamp = np.where(df['timestamp'] == 0,
                                    df['timestamp_y'], df['timestamp'])
            df.address = np.where(df['address'] == 'N/A', df['hostname'],
                                  df['address'])

            drop_cols.extend(['status_y', 'timestamp_y'])

        df = self._handle_user_query_str(df, user_query)
        return df.drop(columns=drop_cols)

    def summarize(self, **kwargs):
        """Summarize device information across namespace"""

        self._init_summarize(self.iobj.table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
        ]

        self._summarize_on_add_with_query = [
            ('downDeviceCnt', 'status == "dead"', 'hostname', 'nunique'),
            ('pollerFailDeviceCnt', 'status == "pollfail"', 'hostname', 'nunique'),
        ]

        self._summarize_on_add_list_or_count = [
            ('vendorCnt', 'vendor'),
            ('modelCnt', 'model'),
            ('archCnt', 'architecture'),
            ('versionCnt', 'version'),
        ]

        self.summary_df = self.iobj.humanize_fields(self.summary_df)

        self._summarize_on_add_stat = [
            ('upTimeStat', 'status != "pollfail"', 'uptime')
        ]

        self._gen_summarize_data()
        self._post_summarize(check_empty_col='deviceCnt')
        return self.ns_df.convert_dtypes()
