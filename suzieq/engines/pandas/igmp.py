from typing import List
from ipaddress import ip_address, ip_network
from collections import defaultdict

import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class IgmpObj(SqPandasEngine):
    '''Backend class to handle manipulating mroutes table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'igmp'

    def get(self, **kwargs):
        '''Return the igmp table for the given filters'''

        source = kwargs.pop('source', '')
        group = kwargs.pop('group', '')
        vrf = kwargs.pop('vrf', '')
        user_query = kwargs.pop('query_str', '')
        columns = kwargs.pop('columns', ['default'])
        fields = self.schema.get_display_fields(columns)

        addnl_fields = ['source', 'group', 'interfaceList', 'querier', 'vrf']

        df = super().get(addnl_fields=addnl_fields, source=source,
                         ipvers=ipvers, columns=fields, **kwargs)

        if user_query:
            df = self._handle_user_query_str(df, user_query)

        return df[fields]
