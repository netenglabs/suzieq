import typing

from suzieq.sqobjects import basicobj


class FsObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         namespace, columns, context=context, table='fs')
        self._sort_fields = ['namespace', 'hostname', 'device']
        self._cat_fields = []
        # mountPoint is not a partition key
        self._ign_key_fields = ["mountPoint"]
