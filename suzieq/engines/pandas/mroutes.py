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

        addnl_fields = []

        # /32 routes are stored with the /32 prefix, so if user doesn't specify
        # prefix as some folks do, assume /32


        df = super().get(addnl_fields=addnl_fields, source=source,
                         ipvers=ipvers, columns=fields, **kwargs)


        if user_query:
            df = self._handle_user_query_str(df, user_query)

        return df.reset_index(drop=True)[fields]

    # def summarize(self, **kwargs):
    #     '''Summarize routing table info'''

    #     self._init_summarize(**kwargs)
    #     if self.summary_df.empty:
    #         return self.summary_df

    #     self._summarize_on_add_field = [
    #         ('deviceCnt', 'hostname', 'nunique'),
    #         ('uniquePrefixCnt', 'prefix', 'nunique'),
    #         ('uniqueVrfsCnt', 'vrf', 'nunique'),
    #     ]

    #     self._summarize_on_perdevice_stat = [
    #         ('routesPerHostStat', '', 'prefix', 'count')
    #     ]

    #     self._summarize_on_add_with_query = [
    #         ('ifRoutesCnt',
    #          'prefixlen == 30 or prefixlen == 31', 'prefix'),
    #         ('hostRoutesCnt', 'prefixlen == 32', 'prefix'),
    #         ('totalV4RoutesinNs', 'ipvers == 4', 'prefix'),
    #         ('totalV6RoutesinNs', 'ipvers == 6', 'prefix'),
    #     ]

    #     self._summarize_on_add_list_or_count = [
    #         ('routingProtocolCnt', 'protocol'),
    #         ('nexthopCnt', 'numNexthops'),
    #     ]

    #     self._gen_summarize_data()

    #     # Now for the stuff that is specific to routes
    #     routes_per_vrfns = self.summary_df.groupby(by=["namespace", "vrf"])[
    #         "prefix"].count().groupby("namespace")
    #     self._add_stats_to_summary(routes_per_vrfns, 'routesperVrfStat')
    #     self.summary_row_order.append('routesperVrfStat')

    #     device_with_defrt_per_vrfns = self.summary_df \
    #         .query('prefix == "0.0.0.0/0"') \
    #         .groupby(by=["namespace", "vrf"])[
    #             "hostname"].nunique()
    #     devices_per_vrfns = self.summary_df.groupby(by=["namespace", "vrf"])[
    #         "hostname"].nunique()

    #     # pylint: disable=expression-not-assigned
    #     {self.ns[i[0]].update({
    #         "deviceWithNoDefRoute":
    #         device_with_defrt_per_vrfns[i] == devices_per_vrfns[i]})
    #      for i in device_with_defrt_per_vrfns.keys() if i[0] in self.ns.keys()}
    #     self.summary_row_order.append('deviceWithNoDefRoute')

    #     self._post_summarize()
    #     return self.ns_df.convert_dtypes()
