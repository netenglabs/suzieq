from .engineobj import SqEngineObject


class MlagObj(SqEngineObject):
    pass


    def summarize(self, **kwargs):
        self._init_summarize(self.iobj._table, **kwargs)
        if self.summary_df.empty:
            return self.summary_df

        self._add_field_to_summary('hostname', 'count', 'rows')
        for field in ['portsErrDisabled', 'vtepIP', 'peerRole', 'backupActive',
                      'mlagSinglePortsCnt', 'role', 'mlagDualPortsCnt',
                      'state', 'peerMacAddress', 'mlagErrorPortsCnt',
                      'mlagErrorPortsCnt', 'peerLink', 'configSanity',
                      'systemId', 'backupIP', 'peerAddress', 'peerLinkStatus',
                      'domainId']:
            self._add_list_or_count_to_summary(field)


        # have to explode fields that are lists
        self.summary_df = self.summary_df.explode('mlagInterfacesList').dropna(how='any')
        self.nsgrp = self.summary_df.groupby(by=["namespace"])

        for field in ['mlagInterfacesList']:
            self._add_list_or_count_to_summary(field)


        self._post_summarize()
        return self.ns_df.convert_dtypes()