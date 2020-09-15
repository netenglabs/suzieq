from suzieq.sqobjects.basicobj import SqObject


class DeviceObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='device', **kwargs)
