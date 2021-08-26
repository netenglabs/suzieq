import pandas as pd
import numpy as np
from .engineobj import SqPandasEngine
from suzieq.sqobjects import get_sqobject


class InventoryObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'inventory'

    def _common_get_exit_fn(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Common exit work to be done on returning from get

        Args:
            df (pd.DataFrame): The dataframe returned by raw get
            **kwargs: Additional kwargs to be passed to the get call

        Returns:
            pd.DataFrame: The dataframe to be returned to the caller
        """
        if df.empty:
            return df

        query_str = kwargs.get('query_str')
        if query_str:
            df = df.query(query_str)

        return df

    def get(self, **kwargs):
        '''Specific get to replace interface names'''
        user_query = kwargs.pop('query_str', '')

        df = super().get(**kwargs)

        if df.empty:
            return df

        if 'name' in df.columns:
            # Lets see if we can name the ports properly
            df1 = df.query('type == "xcvr"').reset_index(drop=True)
            if df1.empty:
                return self._common_get_exit_fn(df, query_str=user_query,
                                                **kwargs)
            # Lets see if we can name the ports properly
            namespaces = kwargs.get('namespace', [])
            hostnames = kwargs.get('hostname', [])
            ifdf = get_sqobject('interfaces')(context=self.ctxt) \
                .get(namespace=namespaces, hostname=hostnames,
                     columns=['namespace', 'hostname', 'ifname'], type=['ethernet', 'flexible-ethernet'])
            if ifdf.empty:
                return self._common_get_exit_fn(df, query_str=user_query,
                                                **kwargs)
            df1['portNum'] = df1.name.str.split('port-').str[1]
            ifdf['portNum'] = ifdf.ifname.str.split(r'Ethernet|-').str[1]
            df1 = df1.merge(ifdf, on=['namespace', 'hostname', 'portNum'], how='left') \
                .dropna()

            df = df.merge(df1[['namespace', 'hostname', 'name', 'ifname']],
                          on=['namespace', 'hostname', 'name'], how='left') \
                .fillna({'ifname': ''})
            df['name'] = np.where(df.ifname != "", df.ifname, df.name)
            df = df.drop(['ifname'], axis=1, errors='ignore')

        return self._common_get_exit_fn(df, query_str=user_query, **kwargs)
