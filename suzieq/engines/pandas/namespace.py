import pandas as pd

from suzieq.engines.pandas.engineobj import SqPandasEngine


class NamespaceObj(SqPandasEngine):
    '''Backend class to handle ops on virtual table, namespace, with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'namespace'

    def get(self, **kwargs):
        """Get the information requested"""

        kwargs.get('view', self.iobj.view)
        columns = kwargs.pop('columns', ['default'])
        kwargs.pop('addnl_fields', [])
        user_query = kwargs.pop('query_str', '')
        os = kwargs.pop('os', [])
        model = kwargs.pop('model', [])
        vendor = kwargs.pop('vendor', [])
        os_version = kwargs.pop('version', [])
        namespace = kwargs.pop('namespace', [])

        fields = self.schema.get_display_fields(columns)
        df = pd.DataFrame()

        if os or model or vendor or os_version:
            devdf = self._get_table_sqobj('device').get(
                columns=['namespace', 'hostname', 'os', 'model', 'vendor',
                         'version'],
                os=os, model=model, vendor=vendor, version=os_version,
                namespace=namespace, **kwargs)
        else:
            devdf = self._get_table_sqobj('device').get(
                columns=['namespace', 'hostname'], namespace=namespace,
                **kwargs)

        if devdf.empty:
            return df

        namespace = devdf.namespace.unique().tolist()
        dev_nsgrp = devdf.groupby(['namespace'])

        # Get list of namespaces we're polling
        pollerdf = self._get_table_sqobj('sqPoller') \
            .get(columns=['namespace', 'hostname', 'service', 'status',
                          'timestamp'],
                 namespace=namespace)

        if pollerdf.empty:
            return df

        pollerdf = devdf.merge(pollerdf, on=['namespace', 'hostname'])
        nsgrp = pollerdf.groupby(by=['namespace'])
        pollerns = sorted(pollerdf.namespace.unique().tolist())
        newdf = pd.DataFrame({
            'namespace': pollerns,
            'deviceCnt': dev_nsgrp['hostname'].nunique().tolist(),
            'serviceCnt': nsgrp['service'].nunique().tolist()
        })
        errsvc_df = pollerdf.query('status != 0 and status != 200') \
                            .groupby(by=['namespace'])['service'] \
                            .nunique().reset_index()
        newdf = newdf.merge(errsvc_df, on=['namespace'], how='left',
                            suffixes=['', '_y']) \
            .rename({'service': 'errSvcCnt'}, axis=1) \
            .fillna({'errSvcCnt': 0})
        newdf['errSvcCnt'] = newdf['errSvcCnt'].astype(int)

        # What protocols exist
        for table, fld in [('ospf', 'hasOspf'), ('bgp', 'hasBgp'),
                           ('evpnVni', 'hasVxlan'), ('mlag', 'hasMlag')]:
            df = self._get_table_sqobj(table) \
                .get(namespace=pollerns, columns=['namespace', 'hostname'])
            if df.empty:
                newdf[fld] = False
                continue

            df = df.merge(devdf, on=['namespace', 'hostname'])
            if df.empty:
                newdf[fld] = False
                continue

            gotns = df.namespace.unique().tolist()
            newdf[fld] = newdf.apply(
                lambda x, y: x.namespace in y,
                axis=1, args=(gotns,))

        if 'sqvers' in fields:
            newdf['sqvers'] = self.schema.version
        newdf['active'] = True

        # Look for the rest of info only in selected namepaces
        newdf['lastUpdate'] = nsgrp['timestamp'].max() \
            .reset_index()['timestamp']

        newdf = self._handle_user_query_str(newdf, user_query)
        return newdf[fields]

    def summarize(self, **kwargs):
        '''Summarize for network

        Summarize for network is a bit different from the rest of the
        summaries because its not grouped by namespace.
        '''

        df = self.get(**kwargs)

        if df.empty:
            return df

        self.ns = pd.DataFrame({
            'namespacesCnt': [df.namespace.count()],
            'servicePerNsStat': [[df.serviceCnt.min(), df.serviceCnt.max(),
                                  df.serviceCnt.median()]],
            'nsWithMlagCnt': [df.loc[df.hasMlag].shape[0]],
            'nsWithBgpCnt': [df.loc[df.hasBgp].shape[0]],
            'nsWithOspfCnt': [df.loc[df.hasOspf].shape[0]],
            'nsWithVxlanCnt': [df.loc[df.hasVxlan].shape[0]],
            'nsWithErrsvcCnt': [df.loc[df.errSvcCnt != 0].shape[0]],
        })

        # At this point we have a single row with index 0, so rename
        return self.ns.T.rename(columns={0: 'summary'})
