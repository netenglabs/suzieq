import typing

from suzieq.sqobjects import basicobj


class RoutesObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         namespace, columns, context=context, table='routes')
        self._sort_fields = ['hostname', 'vrf', 'prefix']
        self._cat_fields = ['protocol', 'metric']

    def lpm(self, **kwargs):
        '''Get the lpm for the given address'''
        if not kwargs.get("address", None):
            raise AttributeError('ip address is mandatory parameter')
        return self.engine_obj.lpm(**kwargs)
