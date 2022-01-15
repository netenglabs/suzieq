from abc import ABC, abstractmethod
from suzieq.shared.sq_plugin import SqPlugin


class SqEngineObj(SqPlugin, ABC):
    '''Interface class for adding analyzer engine to Suzieq'''

    def __init__(self):
        pass

    @abstractmethod
    def get(self, **kwargs):
        '''Retrieve the data given the constraints provided for the table'''
        raise NotImplementedError

    @abstractmethod
    def summarize(self, **kwargs):
        '''Summarize table info'''
        raise NotImplementedError

    @abstractmethod
    def unique(self, **kwargs):
        '''Return unique values or value counts for provided column'''
        raise NotImplementedError

    @abstractmethod
    def aver(self, **kwargs):
        '''Run pre-defined checks on the data'''
        raise NotImplementedError

    @abstractmethod
    def top(self, **kwargs):
        '''Return top values associated with a numeric column'''
        raise NotImplementedError
