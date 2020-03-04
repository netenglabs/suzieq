import typing

from suzieq.sqobjects import basicobj


class LldpObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         datacenter, columns, context=context, table='lldp')
        self._sort_fields = ['datacenter', 'hostname', 'ifname']
        self._cat_fields = []
