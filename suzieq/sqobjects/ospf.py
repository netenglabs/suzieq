import pandas as pd

from suzieq.sqobjects.basicobj import SqObject
from suzieq.utils import SchemaForTable


class OspfObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='ospf', **kwargs)
        self._addnl_fields = ['passive', 'area', 'state']
        self._addnl_nbr_fields = ['state']

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

    def top(self, what='', n=5, reverse=False, **kwargs) -> pd.DataFrame:
        """Get the list of top/bottom entries of "what" field"""

        if "columns" in kwargs:
            columns = kwargs["columns"]
            del kwargs["columns"]
        else:
            columns = ["default"]

        table_schema = SchemaForTable(self._table, self.all_schemas)
        columns = table_schema.get_display_fields(columns)

        if what == "numChanges" and what not in columns:
            self._addnl_nbr_fields.append(what)

        return self.engine_obj.top(what=what, n=n, reverse=reverse, **kwargs)
