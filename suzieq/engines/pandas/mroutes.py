from typing import List
from ipaddress import ip_address, ip_network
from collections import defaultdict

import numpy as np
import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class MroutesObj(SqPandasEngine):
    '''Backend class to handle manipulating mroutes table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'mroutes'

    def get(self, **kwargs):
        '''Return the mroutes table for the given filters'''

        source = kwargs.pop('source', '')
        group = kwargs.pop('group', '')
        vrf = kwargs.pop('vrf', '')
        ipvers = kwargs.pop('ipvers', '')
        user_query = kwargs.pop('query_str', '')

        columns = kwargs.pop('columns', ['default'])
        fields = self.schema.get_display_fields(columns)

        print(fields)

        addnl_fields = ['source', 'group', 'rpfInterface', 'oifList', 'rpNeighbor']

        # /32 routes are stored with the /32 prefix, so if user doesn't specify
        # prefix as some folks do, assume /32


        df = super().get(addnl_fields=addnl_fields, source=source,
                         ipvers=ipvers, columns=fields, **kwargs)


        if user_query:
            df = self._handle_user_query_str(df, user_query)

        return df[fields]
