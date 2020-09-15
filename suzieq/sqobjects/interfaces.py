import pandas as pd

from suzieq.sqobjects.basicobj import SqObject


class IfObj(SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='interfaces', **kwargs)

    def summarize(self, namespace=[]):
        """Summarize routing info for one or more namespaces"""

        return self.engine_obj.summarize(namespace=namespace)

    def aver(self, what='mtu-match', **kwargs) -> pd.DataFrame:
        """Assert that interfaces are in good state"""
        return self.engine_obj.aver(what=what, **kwargs)
