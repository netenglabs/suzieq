from suzieq.sqobjects.basicobj import SqObject


class AddressObj(SqObject):

    def __init__(self, **kwargs):
        super().__init__(table='address', **kwargs)
