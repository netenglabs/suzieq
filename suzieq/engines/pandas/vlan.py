import pandas as pd

from .engineobj import SqEngineObject


class VlanObj(SqEngineObject):

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
