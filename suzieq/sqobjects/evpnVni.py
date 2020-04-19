import typing

from suzieq.sqobjects import basicobj


class EvpnvniObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         namespace, columns, context=context, table='evpnVni')
        self._sort_fields = ['namespace', 'hostname', 'vni']
        self._cat_fields = []

    def aver(self, **kwargs):
        """Assert that the BGP state is OK"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.aver(**kwargs)
