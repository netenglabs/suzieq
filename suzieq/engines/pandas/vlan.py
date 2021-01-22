import numpy as np

from .engineobj import SqPandasEngine


class VlanObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'vlan'

    def get(self, **kwargs):
        """Get VLAN info based on specified keywords"""

        # ifname is a deprecated field, from version 1.0
        # vlanName is the correct fieldname. SO we need to do magic
        # to fix this. And thats why this routine exists

        dropcols = []
        addnl_fields = kwargs.pop('addnl_fields', [])
        columns = kwargs.pop('columns', [])
        if (columns != ['*'] and (columns == ['default'] or
                                  'ifname' not in columns)):
            if 'ifname' not in addnl_fields:
                addnl_fields.append('ifname')
                dropcols.append('ifname')

        df = super().get(addnl_fields=addnl_fields,
                         merge_fields={'ifname': 'vlanName'},
                         **kwargs)
        if not df.empty:
            df.drop(columns=dropcols, errors='ignore', inplace=True)

        return df

    def summarize(self, **kwargs):
        """Describe the IP Address data"""

        self._init_summarize(self.iobj.table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('uniqueVlanCnt', 'vlan', 'nunique')
        ]

        self._summarize_on_add_with_query = [
            ('activeVlanCnt', 'state == "active"', 'vlan', 'nunique'),
            ('suspendedVlanCnt', 'state == "suspend"', 'vlan', 'nunique')
        ]

        self._summarize_on_perdevice_stat = [
            ('vlanPerDeviceStat', '', 'vlan', 'count')
        ]

        self._gen_summarize_data()

        self._add_stats_to_summary(self.summary_df.groupby(
            by=['namespace', 'vlan'])['interfaces'].count(), 'ifPerVlanStat',
            True)
        self.summary_row_order.append('ifPerVlanStat')

        self._post_summarize()
        return self.ns_df.convert_dtypes()
