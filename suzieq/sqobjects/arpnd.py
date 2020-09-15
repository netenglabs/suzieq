from suzieq.sqobjects.basicobj import SqObject


class ArpndObj(SqObject):

    def __init__(self, **kwargs):
        super().__init__(table='arpnd', **kwargs)
