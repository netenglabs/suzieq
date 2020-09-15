from suzieq.sqobjects.basicobj import SqObject


class TopcpuObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='topcpu', **kwargs)
