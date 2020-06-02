from .engineobj import SqEngineObject


class MacsObj(SqEngineObject):

    def get(self, **kwargs):
        if not self.iobj._table:
            raise NotImplementedError

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.iobj._sort_fields

        remoteOnly = False
        if kwargs.get('remoteVtepIp', []):
            if kwargs['remoteVtepIp'] == ['any']:
                remoteOnly = True
                del kwargs['remoteVtepIp']

        df = self.get_valid_df(self.iobj._table, sort_fields, **kwargs)
        if remoteOnly:
            return df.query("remoteVtepIp != ''")

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
            ('herPerVtepStat', 'macaddr == "00:00:00:00:00:00"', 'macaddr',
             'count')
        ]

        return super().summarize(**kwargs)
