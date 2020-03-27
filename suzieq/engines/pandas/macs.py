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

