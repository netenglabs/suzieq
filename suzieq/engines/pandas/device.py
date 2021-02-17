import numpy as np
from .engineobj import SqPandasEngine


class DeviceObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'device'

    def get(self, **kwargs):
        """Get the information requested"""
        view = kwargs.get('view', 'latest')
        columns = kwargs.get('columns', ['default'])
        addnl_fields = kwargs.pop('addnl_fields', [])
        drop_cols = []

        if 'active' not in addnl_fields+columns and columns != ['*']:
            addnl_fields.append('active')
            drop_cols.append('active')

        df = super().get(active_only=False, addnl_fields=addnl_fields,
                         **kwargs)
        if view == 'latest' and 'status' in df.columns:
            df['status'] = np.where(df.active, df['status'], 'dead')
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
            ('downDeviceCnt', 'status == "dead"', 'hostname', 'nunique')
        ]

        self._summarize_on_add_list_or_count = [
            ('vendorCnt', 'vendor'),
            ('modelCnt', 'model'),
            ('archCnt', 'architecture'),
            ('versionCnt', 'version'),
        ]

        self.summary_df = self.iobj.humanize_fields(self.summary_df)

        self._summarize_on_add_stat = [
            ('upTimeStat', '', 'uptime')
        ]

        self._gen_summarize_data()
        self._post_summarize(check_empty_col='deviceCnt')
        return self.ns_df.convert_dtypes()
