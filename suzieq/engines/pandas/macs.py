from .engineobj import SqPandasEngine


class MacsObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'macs'

    def get(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        remoteOnly = False
        localOnly = kwargs.pop('localOnly', False)
        vtep = kwargs.get('remoteVtepIp', [])
        if vtep:
            if kwargs['remoteVtepIp'] == ['any']:
                del kwargs['remoteVtepIp']
                remoteOnly = True

        df = self.get_valid_df(self.iobj._table, **kwargs)
        if remoteOnly:
            return df.query("remoteVtepIp != ''")
        elif localOnly:
            return df.query("remoteVtepIp == ''")

        return df

    def summarize(self, **kwargs):
        """Summarize the MAC table info"""

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('totalMacsinNSCnt', 'hostname', 'count'),
            ('uniqueMacCnt', 'macaddr', 'nunique'),
        ]

        self._summarize_on_perdevice_stat = [
            ('uniqueVlanperHostStat', 'vlan != 0 and vlan != ""', 'vlan',
             'nunique'),
        ]

        return super().summarize(**kwargs)
