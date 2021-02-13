from suzieq.sqobjects.basicobj import SqObject
import pandas as pd


class RoutesObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='routes', **kwargs)
        self._addnl_filter = 'metric != 4278198272'
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'prefix',
                                'vrf', 'protocol', 'prefixlen', 'ipvers',
                                'add_filter', 'address', 'query_str']

    def lpm(self, **kwargs):
        '''Get the lpm for the given address'''
        if not kwargs.get("address", None):
            raise AttributeError('ip address is mandatory parameter')
        if isinstance(kwargs['address'], list):
            if len(kwargs['address']) > 1:
                raise AttributeError('Just one address at a time')
            kwargs['address'] = kwargs['address'][0]
        return self.engine.lpm(**kwargs)

    def summarize(self, namespace=[], vrf=[], hostname=[], query_str=''):
        """Summarize routing info for one or more namespaces"""
        if self.columns != ["default"]:
            self.summarize_df = pd.DataFrame(
                {'error':
                 ['ERROR: You cannot specify columns with summarize']})
            return self.summarize_df
        return self.engine.summarize(namespace=namespace, vrf=vrf,
                                     query_str=query_str,
                                     hostname=hostname)
