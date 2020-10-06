from suzieq.sqobjects.basicobj import SqObject


class RoutesObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='routes', **kwargs)
        self._addnl_filter = 'metric != 4278198272'
        self._valid_get_args = ['namespace', 'hostname', 'prefix', 
                                'vrf', 'protocol', 'ipvers', 'prefixlen',
                                'add_filter']

    def lpm(self, **kwargs):
        '''Get the lpm for the given address'''
        if not kwargs.get("address", None):
            raise AttributeError('ip address is mandatory parameter')
        return self.engine_obj.lpm(**kwargs)

    def summarize(self, namespace=[], vrf=[]):
        """Summarize routing info for one or more namespaces"""

        return self.engine_obj.summarize(namespace=namespace, vrf=vrf)
