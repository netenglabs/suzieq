from suzieq.sqobjects.basicobj import SqObject


class MlagObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='mlag', **kwargs)
