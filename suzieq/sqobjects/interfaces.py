import pandas as pd
import typing

from suzieq.sqobjects import basicobj


class IfObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', datacenter: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         datacenter, columns, context=context,
                         table='interfaces')
        self._sort_fields = ['datacenter', 'hostname', 'ifname']
        self._cat_fields = ['mtu']

    def aver(self, what='mtu-match', **kwargs) -> pd.DataFrame:
        """Assert that interfaces are in good state"""
        return self.engine_obj.aver(what=what, **kwargs)

    def top(self, what='transitions', n=5, **kwargs) -> pd.DataFrame:
        """Get the list of top link changes"""
        return self.engine_obj.top(what=what, n=n, **kwargs)
