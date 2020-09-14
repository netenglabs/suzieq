import typing
from suzieq.sqobjects.basicobj import SqObject


class PathObj(SqObject):
    def __init__(
            self,
            engine: str = "",
            hostname: typing.List[str] = [],
            start_time: str = "",
            end_time: str = "",
            view: str = "latest",
            namespace: typing.List[str] = [],
            columns: typing.List[str] = ["default"],
            context=None,
    ) -> None:
        super().__init__(
            engine,
            hostname,
            start_time,
            end_time,
            view,
            namespace,
            columns,
            context=context,
            table='path',
        )
        self._sort_fields = ["namespace", "hostname", "pathid"]
        self._cat_fields = []

    def get(self, **kwargs):

        return self.engine_obj.get(**kwargs)

    def summarize(self, **kwargs):
        """Summarize topology info for one or more namespaces"""

        return self.engine_obj.summarize(**kwargs)
