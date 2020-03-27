from .engineobj import SqEngineObject


class ArpndObj(SqEngineObject):
    pass

    def summarize(self, **kwargs):
        self.summary_row_order = ['hostname', 'namespace', 'macaddr',
                                  'ipAddress', 'oif', 'state', 'offload']

        return super().summarize(**kwargs)
