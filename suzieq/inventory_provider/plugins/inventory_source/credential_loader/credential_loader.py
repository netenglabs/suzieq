from abc import abstractclassmethod
from suzieq.shared.sq_plugin import SqPlugin

class CredentialLoader(SqPlugin):
    def __init__(self, init_data) -> None:
        self.init(init_data)
        pass

    def init(self, init_data):
        pass

    @abstractclassmethod
    def load(self, data):
        pass
