from suzieq.sqobjects.basicobj import SqObject


class TopmemObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='topmem', **kwargs)
