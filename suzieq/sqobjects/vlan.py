from suzieq.sqobjects.basicobj import SqObject


class VlanObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='vlan', **kwargs)
