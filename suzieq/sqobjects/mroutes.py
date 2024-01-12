from suzieq.sqobjects.basicobj import SqObject


class MroutesObj(SqObject):
    """The object providing access to the mroutes table."""

    def __init__(self, **kwargs):
        super().__init__(table="mroutes", **kwargs)
        self._valid_get_args = [
            "namespace",
            "hostname",
            "columns",
            "source",
            "group",
            "vrf",
            "rpfInterface",
            "oifList",
            "ipvers",
            "rpfneighbor",
            "query_str",
        ]
