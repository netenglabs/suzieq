import typing
import pandas as pd

from suzieq.sqobjects import basicobj
from suzieq.utils import SchemaForTable


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
        self._addnl_fields = ['passive', 'area', 'state', 'origIfname']
        self._addnl_nbr_fields = ['state', 'origIfname']

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

    def top(self, what='', n=5, reverse=False,
            **kwargs) -> pd.DataFrame:
        """Get the list of top/bottom entries of "what" field"""

        if "columns" in kwargs:
            columns = kwargs["columns"]
            del kwargs["columns"]
        else:
            columns = ["default"]

        table_schema = SchemaForTable(self._table, self.schemas)
        columns = table_schema.get_display_fields(columns)

        if what == "numChanges" and what not in columns:
            self._addnl_nbr_fields.append(what)

        return self.engine_obj.top(what=what, n=n, reverse=reverse, **kwargs)
