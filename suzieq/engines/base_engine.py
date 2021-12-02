from abc import ABC, abstractmethod
from suzieq.shared.sq_plugin import SqPlugin


class SqEngineObj(SqPlugin, ABC):
    '''Interface class for adding analyzer engine to Suzieq'''

    def __init__(self):
        pass

    @abstractmethod
    def get(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def summarize(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def unique(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def aver(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def top(self, **kwargs):
        raise NotImplementedError
