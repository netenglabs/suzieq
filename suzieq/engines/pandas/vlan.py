import numpy as np

from .engineobj import SqEngineObject


class VlanObj(SqEngineObject):

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

        self._add_field_to_summary('hostname', 'count', 'deviceCnt')

        if not self.summary_df.empty:
            for field in ['vlan']:
                self._add_list_or_count_to_summary(field,
                                                   field_name='uniqueVlanCnt')

        self._post_summarize()
        return self.ns_df.convert_dtypes()
