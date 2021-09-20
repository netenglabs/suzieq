import pandas as pd
import numpy as np
import operator
from packaging import version
from .engineobj import SqPandasEngine
from suzieq.sqobjects.sqPoller import SqPollerObj
from suzieq.utils import humanize_timestamp


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
        status = kwargs.pop('status', '')
        os_version = kwargs.pop('version', '')
        vendor = kwargs.get('vendor', '')
        model = kwargs.get('model', '')
        os = kwargs.get('os', '')

        drop_cols = []

        if 'active' not in addnl_fields+columns and columns != ['*']:
            addnl_fields.append('active')
            drop_cols.append('active')

        # os is not included in the default column list. Why? I was dumb
        if (columns == ['default'] and os) or (os and 'os' not in columns):
            addnl_fields.append('os')
            drop_cols.append('os')

        for col in ['namespace', 'hostname', 'status', 'address']:
            if (not ((columns == ['default']) or (columns == ['*'])) and
                    col not in columns):
                addnl_fields.append(col)
                drop_cols.append(col)

        if columns == ['*'] or 'uptime' in columns:
            if columns != ['*'] and 'bootupTimestamp' not in columns:
                addnl_fields.append('bootupTimestamp')
                drop_cols.append('bootupTimestamp')

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
                .fillna({'bootupTimestamp': 0, 'timestamp': 0,
                         'active': True}) \
                .fillna('N/A')

            df.status = np.where(
                (df['status_y'] != 0) & (df['status_y'] != 200) &
                (df['status'] == "N/A"),
                'neverpoll', df['status'])
            df.timestamp = np.where(df['timestamp'] == 0,
                                    df['timestamp_y'], df['timestamp'])
            if 'address' in df.columns:
                df.address = np.where(df['address'] == 'N/A', df['hostname'],
                                      df['address'])

            drop_cols.extend(['status_y', 'timestamp_y'])

            if 'uptime' in columns or columns == ['*']:
                uptime_cols = (df['timestamp'] -
                               humanize_timestamp(df['bootupTimestamp']*1000,
                               self.cfg.get('analyzer', {}).get('timezone', None)))
                uptime_cols = pd.to_timedelta(uptime_cols, unit='s')
                df.insert(len(df.columns)-1, 'uptime', uptime_cols)

        # The poller merge kills the filtering we did earlier, so redo:
        if status:
            df = df.loc[df.status.isin(status)]
        if vendor:
            df = df.loc[df.vendor.isin(vendor)]
        if model:
            df = df.loc[df.model.isin(model)]
        if os:
            df = df.loc[df.os.isin(os)]
        if os_version:
            opdict = {'>': operator.gt, '<': operator.lt, '>=': operator.ge,
                      '<=': operator.le, '=': operator.eq, '!=': operator.ne}
            op = operator.eq
            for elem in opdict:
                if os_version.startswith(elem):
                    os_version = os_version.replace(elem, '')
                    op = opdict[elem]
                    break

            df = df.loc[df.version.apply(
                lambda x: op(version.parse(x), version.parse(os_version)))]

        df = self._handle_user_query_str(df, user_query)

        # if poller has failed completely, Can mess up the order of columns
        cols = self.iobj.schema.get_display_fields(columns)
        if columns == ['default'] and 'timestamp' not in cols:
            cols.append('timestamp')
        if 'sqvers' in cols:
            cols.remove('sqvers')
        return df.drop(columns=drop_cols, errors='ignore')[cols]

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
            ('unpolledDeviceCnt', 'status == "neverpoll"', 'hostname',
             'nunique'),
        ]

        self._summarize_on_add_list_or_count = [
            ('vendorCnt', 'vendor'),
            ('modelCnt', 'model'),
            ('archCnt', 'architecture'),
            ('versionCnt', 'version'),
        ]

        self.summary_df = self.iobj.humanize_fields(self.summary_df)

        self._summarize_on_add_stat = [
            ('upTimeStat', 'status != "neverpoll"', 'uptime')
        ]

        self._gen_summarize_data()
        self._post_summarize(check_empty_col='deviceCnt')
        return self.ns_df.convert_dtypes()
