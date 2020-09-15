from suzieq.sqobjects.basicobj import SqObject


class EvpnvniObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='evpnVni', **kwargs)

    def aver(self, **kwargs):
        """Assert that the BGP state is OK"""

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.aver(**kwargs)
