import typing
import pandas as pd

from suzieq.sqobjects import basicobj


class OspfObj(basicobj.SqObject):

    def __init__(self, engine: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None) -> None:
        super().__init__(engine, hostname, start_time, end_time, view,
                         namespace, columns, context=context, table='ospf')
        self._sort_fields = ['namespace', 'hostname', 'vrf', 'ifname']
        self._cat_fields = []
        self._addnl_fields = ['passive', 'area', 'state']

    def get(self, **kwargs):

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.get(**kwargs)

    def summarize(self, **kwargs):
        """Describe the data"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.summarize(**kwargs)

    def aver(self, **kwargs):
        """Assert that the OSPF state is OK"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.aver(**kwargs)

    def top(self, what='transitions', n=5, **kwargs) -> pd.DataFrame:
        """Get the list of top stuff about OSPF"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.top(what=what, n=n, **kwargs)
