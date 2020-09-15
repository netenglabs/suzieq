from suzieq.sqobjects.basicobj import SqObject


class SqPollerObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='sqPoller', **kwargs)
