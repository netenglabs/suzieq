from suzieq.sqobjects.basicobj import SqObject


class FsObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='fs', **kwargs)
