import pandas as pd
import typing

from suzieq.sqobjects import basicobj


class IfObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         namespace, columns, context=context,
                         table='interfaces')
        self._sort_fields = ['namespace', 'hostname', 'ifname']
        self._cat_fields = ['mtu']
        self._addnl_fields = ['origIfname']

    def summarize(self, namespace=[]):
        """Summarize routing info for one or more namespaces"""

        return self.engine_obj.summarize(namespace=namespace)

    def aver(self, what='mtu-match', **kwargs) -> pd.DataFrame:
        """Assert that interfaces are in good state"""
        return self.engine_obj.aver(what=what, **kwargs)
